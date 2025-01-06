import logging
import time
from datetime import datetime
from typing import List, Optional

import anthropic
import keybert
import requests
from markdownify import markdownify
from raindropiopy import API, CollectionRef, Raindrop, RaindropType
from slugify import slugify

from .api_utils import safe_api_call
from .models import Bookmark
from .youtube_processing import extract_video_id, generate_paper_summary, get_transcript


class BookmarkProcessor:
    """Core processor for Raindrop bookmarks."""

    def __init__(
        self,
        raindrop_token: str,
        key_bert_model: keybert.KeyBERT,
        claude_client: anthropic.Client,
        logger: Optional[logging.Logger] = None,
    ):
        self.raindrop_token = raindrop_token
        self.key_bert_model = key_bert_model
        self.claude_client = claude_client
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("BookmarkProcessor initialized successfully")

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text using KeyBERT."""
        self.logger.info("Starting keyword extraction")
        if len(text.split(" ")) > 1000:
            text = " ".join(text.split(" ")[:1000])
            self.logger.info("Text truncated to 1000 words for keyword extraction")

        try:
            keywords = safe_api_call(
                self.key_bert_model.extract_keywords,
                text,
                keyphrase_ngram_range=(1, 2),
                max_retries=3,
                logger=self.logger,
            )
            if isinstance(keywords, list):
                keywords = keywords[0]
            keywords = [slugify(keyword) for keyword in keywords]
            self.logger.info(f"Successfully extracted {len(keywords)} keywords")
            return keywords
        except Exception as e:
            self.logger.error(f"Error extracting keywords: {e}")
            return []

    def get_item_text(self, item: Raindrop) -> Optional[str]:
        """Extract text content from a Raindrop item."""
        self.logger.info(f"Extracting text from bookmark: {item.title}")
        try:
            if item.type == RaindropType.video and "youtube.com" in item.link:
                self.logger.info("Processing as YouTube video")
                return self.process_youtube_video(item)

            elif item.type == RaindropType.link:
                self.logger.info("Processing as web link")

                def fetch_webpage():
                    response = requests.get(item.link)
                    response.raise_for_status()
                    return response.text

                webpage_content = safe_api_call(
                    fetch_webpage,
                    max_retries=3,
                    logger=self.logger,
                )
                if webpage_content:
                    self.logger.info("Successfully fetched webpage content")
                    return markdownify(webpage_content, strip=["a"])
                self.logger.error("Failed to fetch webpage content")

            elif item.type == RaindropType.article:
                self.logger.info("Processing as article")
                if item.excerpt:
                    self.logger.info("Using article excerpt")
                    return item.excerpt
                self.logger.error("No excerpt available for article")

            elif item.type == RaindropType.video:
                self.logger.info("Processing as non-YouTube video")
                if item.note:
                    self.logger.info("Using video note")
                    return item.note
                self.logger.error("No note available for video")

            self.logger.error(f"No text found for {item.title}")
            return None

        except Exception as e:
            self.logger.error(f"Error processing {item.title}: {e}")
            return None

    def process_bookmark(
        self, item: Raindrop, extract_tags: bool = True, generate_summary: bool = True
    ) -> Optional[Bookmark]:
        """Process a single bookmark."""
        self.logger.info(f"Processing bookmark: {item.title}")
        try:
            text = self.get_item_text(item)
            if not text:
                self.logger.error("Failed to extract text content")
                return None

            new_tags = []
            summary = None

            if extract_tags:
                self.logger.info("Extracting keywords")
                new_tags = self.extract_keywords(text)
                self.logger.info(f"Extracted keywords: {new_tags}")

            if generate_summary:
                self.logger.info("Generating summary")
                if item.type == RaindropType.video and "youtube.com" in item.link:
                    summary = text  # text is already the summary for YouTube videos
                    self.logger.info("Using YouTube transcript as summary")
                else:
                    summary = generate_paper_summary(text, self.claude_client)
                    self.logger.info("Generated new summary")

            # Add appropriate processing tag
            processing_tags = ["_processed"]
            if item.type == RaindropType.video and "youtube.com" in item.link:
                processing_tags.append("_video_summarized")

            self.logger.info(f"Successfully processed bookmark: {item.title}")
            return Bookmark(
                id=item.id,
                link=item.link,
                title=item.title,
                excerpt=item.excerpt,
                note=item.note,
                tags=list(set(item.tags + new_tags + processing_tags)),
                summary=summary,
                created_at=datetime.now(),
                updated_at=None,
            )

        except Exception as e:
            self.logger.error(f"Error processing bookmark {item.title}: {e}")
            return None

    def update_raindrop(self, bookmark: Bookmark) -> bool:
        """Update a Raindrop bookmark with new tags and summary."""
        self.logger.info(f"Updating bookmark: {bookmark.title}")
        try:
            with API(self.raindrop_token) as api:

                def update_bookmark():
                    return Raindrop.update(
                        api,
                        id=int(bookmark.id),
                        tags=bookmark.tags,
                        note=(bookmark.summary or "") + "\n\n" + (bookmark.note or ""),
                    )

                result = safe_api_call(update_bookmark, max_retries=5, logger=self.logger)
                if result:
                    self.logger.info(f"Successfully updated bookmark: {bookmark.title}")
                    return True
                return False

        except Exception as e:
            self.logger.error(f"Error updating bookmark {bookmark.title}: {e}")
            return False

    def process_bookmarks(
        self,
        bookmark_ids: List[str],
        extract_tags: bool = True,
        generate_summary: bool = True,
        update_raindrop: bool = True,
    ) -> tuple[List[Bookmark], List[str]]:
        """Process multiple bookmarks."""
        self.logger.info(f"Starting batch processing of {len(bookmark_ids)} bookmarks")
        processed_bookmarks = []
        failed_bookmarks = []

        with API(self.raindrop_token) as api:
            for bookmark_id in bookmark_ids:
                self.logger.info(f"Processing bookmark ID: {bookmark_id}")
                try:

                    def search_bookmark():
                        for bm in Raindrop.search(api):
                            if bm.id == int(bookmark_id):
                                return bm
                        return None

                    item = safe_api_call(
                        search_bookmark,
                        max_retries=5,
                        logger=self.logger,
                    )

                    if not item:
                        self.logger.error(f"Bookmark {bookmark_id} not found")
                        failed_bookmarks.append(bookmark_id)
                        continue

                    processed = self.process_bookmark(item, extract_tags, generate_summary)
                    if processed:
                        if update_raindrop:
                            if self.update_raindrop(processed):
                                processed_bookmarks.append(processed)
                                self.logger.info(
                                    f"Successfully processed and updated: {item.title}"
                                )
                            else:
                                failed_bookmarks.append(bookmark_id)
                                self.logger.error(f"Failed to update: {item.title}")
                        else:
                            processed_bookmarks.append(processed)
                            self.logger.info(f"Successfully processed: {item.title}")
                    else:
                        failed_bookmarks.append(bookmark_id)
                        self.logger.error(f"Failed to process: {item.title}")

                except Exception as e:
                    self.logger.error(f"Error processing bookmark {bookmark_id}: {e}")
                    failed_bookmarks.append(bookmark_id)

            self.logger.info(
                f"Batch processing completed. Processed: {len(processed_bookmarks)}, Failed: {len(failed_bookmarks)}"
            )
            return processed_bookmarks, failed_bookmarks
