import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

import anthropic
import keybert
import keybert.llm
import openai
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel
from raindropiopy import API, CollectionRef, Raindrop, RaindropType

from .models import (
    BatchProcessingResponse,
    BatchProcessingStatus,
    Bookmark,
    BookmarkProcessingRequest,
    BookmarkProcessingResponse,
    ProcessingHistoryResponse,
    ProcessingStatus,
)
from .processors import BookmarkProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize global clients
processor: BookmarkProcessor | None = None
anthropic_client: anthropic.Client | None = None
key_bert_model: keybert.KeyBERT | None = None

# In-memory store for batch processing tasks
processing_tasks: Dict[str, BatchProcessingStatus] = {}

# Add after other imports
load_dotenv()  # Load environment variables from .env file


class BookmarkList(BaseModel):
    """Response model for bookmark list."""

    bookmarks: List[Bookmark]
    total_count: int
    error: Optional[str] = None


def check_required_env_vars() -> Optional[str]:
    """Check if all required environment variables are set."""
    required_vars = ["RAINDROP_TOKEN", "OPENAI_API_KEY", "OPENAI_MODEL", "ANTHROPIC_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        return f"Missing required environment variables: {', '.join(missing_vars)}"
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    global processor, anthropic_client, key_bert_model
    try:
        logger.info("Checking environment variables...")
        if error := check_required_env_vars():
            raise ValueError(error)

        logger.info("Initializing services...")

        # Initialize OpenAI client for KeyBERT
        logger.info("Initializing OpenAI client")
        openai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        llm = keybert.llm.OpenAI(openai_client, model=os.environ["OPENAI_MODEL"], chat=True)
        key_bert_model = keybert.KeyBERT(llm=keybert.KeyLLM(llm))
        logger.info("Successfully initialized KeyBERT with OpenAI")

        # Initialize Claude client
        logger.info("Initializing Claude client")
        anthropic_client = anthropic.Client(api_key=os.environ["ANTHROPIC_API_KEY"])
        logger.info("Successfully initialized Claude client")

        # Create processor instance
        logger.info("Creating BookmarkProcessor instance")
        processor = BookmarkProcessor(
            os.environ["RAINDROP_TOKEN"],
            key_bert_model,
            anthropic_client,
            logger,
        )
        logger.info("Successfully initialized all services")
        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        logger.info("Cleaning up services")
        processor = None
        anthropic_client = None
        key_bert_model = None
        logger.info("Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="Raindrop Bookmark Processor",
    description="API for processing Raindrop.io bookmarks with automatic tag extraction and summarization",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/bookmarks/", response_model=BookmarkList)
async def get_bookmarks(
    collection: str = "unsorted",
    include_processed: bool = False,
) -> BookmarkList:
    """Get bookmarks from Raindrop.io."""
    if not processor:
        logger.error("Services not initialized")
        return BookmarkList(bookmarks=[], total_count=0, error="Services not initialized")

    try:
        logger.info(f"Fetching bookmarks from {collection} collection")
        with API(os.environ["RAINDROP_TOKEN"]) as api:
            # Determine which collection to search
            if collection.lower() == "unsorted":
                logger.info("Searching unsorted collection")
                bookmarks = list(Raindrop.search(api, collection=CollectionRef.Unsorted))
            else:
                logger.info("Searching all collections")
                bookmarks = list(Raindrop.search(api))

            logger.info(f"Found {len(bookmarks)} bookmarks")

            # Filter out processed bookmarks if requested
            if not include_processed:
                logger.info("Filtering out processed bookmarks")
                original_count = len(bookmarks)
                bookmarks = [
                    bookmark
                    for bookmark in bookmarks
                    if "_processed" not in bookmark.tags
                    and (
                        bookmark.type != RaindropType.video
                        or "youtube.com" not in bookmark.link
                        or "_video_summarized" not in bookmark.tags
                    )
                ]
                logger.info(f"Filtered {original_count - len(bookmarks)} processed bookmarks")

            # Convert to Bookmark models
            logger.info("Converting to Bookmark models")
            bookmark_models = [
                Bookmark(
                    id=str(bookmark.id),  # Ensure ID is string
                    link=bookmark.link,
                    title=bookmark.title,
                    excerpt=bookmark.excerpt,
                    note=bookmark.note,
                    tags=bookmark.tags,
                    summary=None,
                    created_at=bookmark.created,  # Use actual creation time
                    updated_at=bookmark.last_update,  # Use actual update time
                    is_processed="_processed" in bookmark.tags,  # Add processing status
                    type=bookmark.type,  # Add bookmark type
                )
                for bookmark in bookmarks
            ]

            logger.info(f"Successfully prepared {len(bookmark_models)} bookmarks")
            return BookmarkList(
                bookmarks=bookmark_models, total_count=len(bookmark_models), error=None
            )

    except Exception as e:
        error_msg = f"Failed to fetch bookmarks: {str(e)}"
        logger.error(error_msg)
        return BookmarkList(bookmarks=[], total_count=0, error=error_msg)


@app.post("/process-bookmarks/", response_model=BookmarkProcessingResponse)
async def process_bookmarks(request: BookmarkProcessingRequest) -> BookmarkProcessingResponse:
    """Process a list of Raindrop bookmarks."""
    if not processor:
        logger.error("Services not initialized")
        raise HTTPException(status_code=500, detail="Services not initialized")

    try:
        logger.info(f"Processing {len(request.bookmark_ids)} bookmarks")
        logger.info(
            f"Options: tags={request.extract_tags}, summary={request.generate_summary}, update={request.update_raindrop}"
        )

        start_time = time.time()
        processed_bookmarks, failed_bookmarks = processor.process_bookmarks(
            request.bookmark_ids,
            request.extract_tags,
            request.generate_summary,
            request.update_raindrop,
        )

        processing_time = (time.time() - start_time) * 1000
        logger.info(
            f"Processing completed in {processing_time:.2f}ms. "
            f"Processed: {len(processed_bookmarks)}, Failed: {len(failed_bookmarks)}"
        )

        return BookmarkProcessingResponse(
            processed_bookmarks=processed_bookmarks,
            failed_bookmarks=failed_bookmarks,
            total_processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Error processing bookmarks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process bookmarks: {str(e)}")


async def process_bookmarks_task(
    task_id: str,
    bookmark_ids: List[str],
    extract_tags: bool = True,
    generate_summary: bool = True,
    update_raindrop: bool = True,
) -> None:
    """Background task for processing bookmarks."""
    if not processor:
        logger.error("Services not initialized")
        processing_tasks[task_id].status = ProcessingStatus.FAILED
        processing_tasks[task_id].error_message = "Services not initialized"
        processing_tasks[task_id].end_time = datetime.now()
        return

    try:
        task_status = processing_tasks[task_id]
        task_status.status = ProcessingStatus.IN_PROGRESS

        processed_bookmarks, failed_bookmarks = processor.process_bookmarks(
            bookmark_ids,
            extract_tags,
            generate_summary,
            update_raindrop,
        )

        task_status.processed_bookmarks.extend(processed_bookmarks)
        task_status.failed_bookmarks.extend(failed_bookmarks)
        task_status.processed_count = len(processed_bookmarks)
        task_status.failed_count = len(failed_bookmarks)
        task_status.status = ProcessingStatus.COMPLETED
        task_status.end_time = datetime.now()

    except Exception as e:
        logger.error(f"Error processing bookmarks: {e}")
        task_status.status = ProcessingStatus.FAILED
        task_status.error_message = str(e)
        task_status.end_time = datetime.now()


@app.post("/process-all-bookmarks/", response_model=BatchProcessingResponse)
async def process_all_bookmarks(
    background_tasks: BackgroundTasks,
    extract_tags: bool = True,
    generate_summary: bool = True,
    update_raindrop: bool = True,
) -> BatchProcessingResponse:
    """Start asynchronous processing of all unprocessed bookmarks."""
    if not processor:
        raise HTTPException(status_code=500, detail="Services not initialized")

    try:
        logger.info("Starting batch processing of all unprocessed bookmarks")

        with API(os.environ["RAINDROP_TOKEN"]) as api:
            # Get all unprocessed bookmarks
            unprocessed_bookmarks = [
                bookmark
                for bookmark in Raindrop.search(api)
                if "_processed" not in bookmark.tags
                or (
                    bookmark.type == RaindropType.video
                    and "youtube.com" in bookmark.link
                    and "_video_summarized" not in bookmark.tags
                )
            ]

            if not unprocessed_bookmarks:
                return BatchProcessingResponse(
                    task_id="",
                    status=ProcessingStatus.COMPLETED,
                    message="No unprocessed bookmarks found",
                )

            # Create task ID and status
            task_id = str(uuid.uuid4())
            processing_tasks[task_id] = BatchProcessingStatus(
                task_id=task_id,
                status=ProcessingStatus.PENDING,
                total_bookmarks=len(unprocessed_bookmarks),
                start_time=datetime.now(),
            )

            # Get bookmark IDs and start background task
            bookmark_ids = [str(bookmark.id) for bookmark in unprocessed_bookmarks]
            background_tasks.add_task(
                process_bookmarks_task,
                task_id,
                bookmark_ids,
                extract_tags,
                generate_summary,
                update_raindrop,
            )

            return BatchProcessingResponse(
                task_id=task_id,
                status=ProcessingStatus.PENDING,
                message=f"Processing started for {len(bookmark_ids)} bookmarks",
            )

    except Exception as e:
        logger.error(f"Error initiating batch processing: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate batch processing: {str(e)}",
        )


@app.get("/processing-status/{task_id}", response_model=BatchProcessingStatus)
async def get_processing_status(task_id: str) -> BatchProcessingStatus:
    """Get the status of a batch processing task."""
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return processing_tasks[task_id]


@app.get("/processing-history/", response_model=ProcessingHistoryResponse)
async def get_processing_history() -> ProcessingHistoryResponse:
    """Get the history of processed bookmarks."""
    # Return completed tasks from the processing_tasks store
    completed_tasks = [
        task for task in processing_tasks.values() if task.status == ProcessingStatus.COMPLETED
    ]

    all_processed_bookmarks = []
    for task in completed_tasks:
        all_processed_bookmarks.extend(task.processed_bookmarks)

    return ProcessingHistoryResponse(
        history=all_processed_bookmarks,
        total_count=len(all_processed_bookmarks),
    )
