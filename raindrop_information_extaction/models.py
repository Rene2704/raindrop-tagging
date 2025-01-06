from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Bookmark(BaseModel):
    """Pydantic model for a Raindrop bookmark."""

    id: str
    link: str
    title: str
    excerpt: Optional[str] = None
    note: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProcessingStatus(str, Enum):
    """Enum for batch processing status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchProcessingStatus(BaseModel):
    """Model for tracking batch processing status."""

    task_id: str
    status: ProcessingStatus
    total_bookmarks: int
    processed_count: int = 0
    failed_count: int = 0
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    processed_bookmarks: List[Bookmark] = Field(default_factory=list)
    failed_bookmarks: List[str] = Field(default_factory=list)


class BatchProcessingResponse(BaseModel):
    """Response model for batch processing initiation."""

    task_id: str
    status: ProcessingStatus
    message: str


class BookmarkProcessingRequest(BaseModel):
    """Request model for bookmark processing."""

    bookmark_ids: List[str] = Field(..., description="List of bookmark IDs to process")
    update_raindrop: bool = Field(
        default=True, description="Whether to update the bookmarks in Raindrop.io"
    )
    extract_tags: bool = Field(default=True, description="Whether to extract tags using KeyBERT")
    generate_summary: bool = Field(
        default=True, description="Whether to generate summaries using Claude"
    )


class BookmarkProcessingResponse(BaseModel):
    """Response model for bookmark processing."""

    processed_bookmarks: List[Bookmark]
    failed_bookmarks: List[str] = Field(default_factory=list)
    total_processing_time_ms: float


class ProcessingHistoryResponse(BaseModel):
    """Response model for processing history."""

    history: List[Bookmark] = Field(default_factory=list)
    total_count: int = Field(..., description="Total number of processed bookmarks")
