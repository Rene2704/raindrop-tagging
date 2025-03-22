import json
import logging
import os
from datetime import datetime
from typing import List

import anthropic
import keybert
import requests
import streamlit as st
from raindropiopy import API, CollectionRef, Raindrop

from raindrop_information_extaction.processors import BookmarkProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configure page
st.set_page_config(
    page_title="Raindrop Bookmark Processor",
    page_icon="📚",
    layout="wide",
)


def add_log_message(message: str, level: str = "info"):
    """Add a log message to the session state and log it."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"{timestamp} - {message}"
    st.session_state.log_messages.append((level, log_entry))

    # Log to Python logger
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


# Initialize session state
if "processed_bookmarks" not in st.session_state:
    st.session_state.processed_bookmarks = []
if "failed_bookmarks" not in st.session_state:
    st.session_state.failed_bookmarks = []
if "processing_time" not in st.session_state:
    st.session_state.processing_time = 0
if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = []
if "log_messages" not in st.session_state:
    st.session_state.log_messages = []
if "processor" not in st.session_state:
    try:
        # Initialize processor
        key_bert_model = keybert.KeyBERT()
        claude_client = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

        st.session_state.processor = BookmarkProcessor(
            raindrop_token=os.getenv("RAINDROP_TOKEN"),
            key_bert_model=key_bert_model,
            claude_client=claude_client,
            logger=logger,
        )
        add_log_message("BookmarkProcessor initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize BookmarkProcessor: {str(e)}"
        add_log_message(error_msg, "error")
        st.session_state.processor = None


def get_bookmarks(include_processed: bool = False) -> List[dict]:
    """Fetch bookmarks from the backend API."""
    try:
        add_log_message("Fetching bookmarks from Raindrop.io...")
        with API(os.getenv("RAINDROP_TOKEN")) as api:
            bookmarks = []
            for bookmark in Raindrop.search(api):
                if include_processed or "_processed" not in bookmark.tags:
                    bookmarks.append(
                        {
                            "id": str(bookmark.id),
                            "title": bookmark.title,
                            "tags": bookmark.tags,
                            "is_processed": "_processed" in bookmark.tags,
                        }
                    )
            add_log_message(f"Found {len(bookmarks)} bookmarks")
            return bookmarks
    except Exception as e:
        error_msg = f"Error fetching bookmarks: {str(e)}"
        add_log_message(error_msg, "error")
        st.error(error_msg)
        return []


def process_bookmarks(bookmark_ids: List[str], options: dict) -> None:
    """Process selected bookmarks using the BookmarkProcessor."""
    try:
        if not st.session_state.processor:
            raise ValueError("BookmarkProcessor not initialized")

        start_time = datetime.now()
        add_log_message(f"Starting to process {len(bookmark_ids)} bookmark(s)...")

        with st.spinner(f"Processing {len(bookmark_ids)} bookmark(s)..."):
            # Use the actual processor
            processed_bookmarks, failed_bookmarks = st.session_state.processor.process_bookmarks(
                bookmark_ids=bookmark_ids,
                extract_tags=options["extract_tags"],
                generate_summary=options["generate_summary"],
                update_raindrop=options["update_raindrop"],
            )

            # Update session state with results
            st.session_state.processed_bookmarks = processed_bookmarks
            st.session_state.failed_bookmarks = failed_bookmarks

            # Calculate and store processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            st.session_state.processing_time = processing_time

            # Log results
            add_log_message(
                f"Processing completed: {len(processed_bookmarks)} succeeded, "
                f"{len(failed_bookmarks)} failed"
            )
            add_log_message(f"Total processing time: {processing_time:.2f}ms")

            # Show individual results
            for bookmark_id in processed_bookmarks:
                st.success(f"Processed bookmark {bookmark_id}")
            for bookmark_id in failed_bookmarks:
                st.error(f"Failed to process bookmark {bookmark_id}")

            # Refresh bookmarks after processing
            st.session_state.bookmarks = get_bookmarks(options["include_processed"])

    except Exception as e:
        error_msg = f"Error in processing bookmarks: {str(e)}"
        add_log_message(error_msg, "error")
        st.error(error_msg)


def main():
    """Main Streamlit application."""
    st.title("📚 Raindrop Bookmark Processor")
    st.write(
        """
        Process your Raindrop.io bookmarks to automatically extract tags and generate summaries.
        Choose processing mode and configure options below.
        """
    )

    # Sidebar for options and logs
    with st.sidebar:
        st.header("Processing Options")
        options = {
            "update_raindrop": st.checkbox("Update Raindrop.io bookmarks", value=True),
            "extract_tags": st.checkbox("Extract tags using KeyBERT", value=True),
            "generate_summary": st.checkbox("Generate summaries using Claude", value=True),
            "include_processed": st.checkbox("Show processed bookmarks", value=False),
        }

        # Log display
        st.header("Processing Log")
        log_container = st.empty()

    # Processing mode selection
    mode = st.radio(
        "Select Processing Mode",
        ["View All Unprocessed", "Process Individual", "Process All"],
        horizontal=True,
    )

    # Refresh bookmarks button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 Refresh"):
            add_log_message("Manually refreshing bookmarks...")
            st.session_state.bookmarks = get_bookmarks(options["include_processed"])

    # Load bookmarks if not loaded
    if not st.session_state.bookmarks:
        st.session_state.bookmarks = get_bookmarks(options["include_processed"])

    # Main content based on mode
    if mode == "View All Unprocessed":
        st.subheader("Unprocessed Bookmarks")
        unprocessed = [b for b in st.session_state.bookmarks if not b["is_processed"]]
        if not unprocessed:
            st.info("No unprocessed bookmarks found!")
            add_log_message("No unprocessed bookmarks found", "warning")
        else:
            for bookmark in unprocessed:
                st.write(f"📑 {bookmark['title']}")
                st.write(f"Tags: {', '.join(bookmark['tags'])}")
                st.divider()

    elif mode == "Process Individual":
        st.subheader("Select Bookmarks to Process")
        col1, col2 = st.columns([2, 1])

        with col1:
            selected_bookmarks = []
            for bookmark in st.session_state.bookmarks:
                if not bookmark["is_processed"]:
                    if st.checkbox(f"📑 {bookmark['title']}", key=f"select_{bookmark['id']}"):
                        selected_bookmarks.append(bookmark)

            if selected_bookmarks:
                if st.button("Process Selected", type="primary"):
                    process_bookmarks([b["id"] for b in selected_bookmarks], options)

        with col2:
            if selected_bookmarks:
                st.write("Selected for processing:")
                for bookmark in selected_bookmarks:
                    st.write(f"- {bookmark['title']}")

    else:  # Process All
        st.subheader("Process All Unprocessed Bookmarks")
        unprocessed = [b for b in st.session_state.bookmarks if not b["is_processed"]]

        if not unprocessed:
            st.info("No unprocessed bookmarks found!")
            add_log_message("No unprocessed bookmarks found", "warning")
        else:
            st.write(f"Found {len(unprocessed)} unprocessed bookmarks")
            if st.button("Process All", type="primary"):
                process_bookmarks([b["id"] for b in unprocessed], options)

    # Processing results
    if st.session_state.processed_bookmarks or st.session_state.failed_bookmarks:
        st.divider()
        st.subheader("Processing Results")

        if st.session_state.processed_bookmarks:
            st.success(
                f"Successfully processed {len(st.session_state.processed_bookmarks)} bookmarks "
                f"in {st.session_state.processing_time:.2f}ms"
            )

        if st.session_state.failed_bookmarks:
            st.error(f"Failed to process {len(st.session_state.failed_bookmarks)} bookmarks")

        # Clear results button
        if st.button("Clear Results"):
            st.session_state.processed_bookmarks = []
            st.session_state.failed_bookmarks = []
            st.session_state.processing_time = 0
            st.session_state.log_messages = []
            add_log_message("Cleared processing results")
            st.rerun()

    # Update log display in sidebar
    with log_container:
        for level, message in st.session_state.log_messages[-10:]:  # Show last 10 messages
            if level == "error":
                st.error(message)
            elif level == "warning":
                st.warning(message)
            else:
                st.info(message)


if __name__ == "__main__":
    main()
