import json
import os
from datetime import datetime
from typing import List

import requests
import streamlit as st
from raindropiopy import API, CollectionRef, Raindrop

# Configure page
st.set_page_config(
    page_title="Raindrop Bookmark Processor",
    page_icon="📚",
    layout="wide",
)

# Initialize session state
if "processed_bookmarks" not in st.session_state:
    st.session_state.processed_bookmarks = []
if "failed_bookmarks" not in st.session_state:
    st.session_state.failed_bookmarks = []
if "processing_time" not in st.session_state:
    st.session_state.processing_time = 0


def get_bookmarks(include_processed: bool = False) -> List[dict]:
    """Fetch bookmarks from the backend API."""
    try:
        response = requests.get(
            "http://localhost:8000/bookmarks/",
            params={"include_processed": include_processed},
        )
        response.raise_for_status()
        result = response.json()
        return result["bookmarks"]
    except Exception as e:
        st.error(f"Error fetching bookmarks: {e}")
        return []


def process_bookmarks(bookmark_ids: List[str], options: dict) -> None:
    """Process selected bookmarks using the FastAPI backend."""
    try:
        response = requests.post(
            "http://localhost:8000/process-bookmarks/",
            json={
                "bookmark_ids": bookmark_ids,
                "update_raindrop": options["update_raindrop"],
                "extract_tags": options["extract_tags"],
                "generate_summary": options["generate_summary"],
            },
        )
        response.raise_for_status()
        result = response.json()

        st.session_state.processed_bookmarks = result["processed_bookmarks"]
        st.session_state.failed_bookmarks = result["failed_bookmarks"]
        st.session_state.processing_time = result["total_processing_time_ms"]

    except Exception as e:
        st.error(f"Error processing bookmarks: {e}")


def main():
    """Main Streamlit application."""
    st.title("📚 Raindrop Bookmark Processor")
    st.write(
        """
        Process your Raindrop.io bookmarks to automatically extract tags and generate summaries.
        Select the bookmarks you want to process and configure the processing options below.
        """
    )

    # Sidebar for options
    with st.sidebar:
        st.header("Processing Options")
        options = {
            "update_raindrop": st.checkbox("Update Raindrop.io bookmarks", value=True),
            "extract_tags": st.checkbox("Extract tags using KeyBERT", value=True),
            "generate_summary": st.checkbox("Generate summaries using Claude", value=True),
            "include_processed": st.checkbox("Show processed bookmarks", value=False),
        }

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Select Bookmarks")
        bookmarks = get_bookmarks(options["include_processed"])

        if not bookmarks:
            st.warning(
                "No bookmarks found. Make sure your Raindrop.io token is configured correctly."
            )
            return

        selected_bookmarks = []
        for bookmark in bookmarks:
            if st.checkbox(
                f"{bookmark['title'][:50]}... ({len(bookmark['tags'])} tags)",
                key=bookmark["id"],
            ):
                selected_bookmarks.append(bookmark)

        if selected_bookmarks:
            if st.button("Process Selected Bookmarks"):
                with st.spinner("Processing bookmarks..."):
                    process_bookmarks(
                        [bookmark["id"] for bookmark in selected_bookmarks],
                        options,
                    )

    with col2:
        st.subheader("Processing Results")
        if st.session_state.processed_bookmarks:
            st.success(
                f"Successfully processed {len(st.session_state.processed_bookmarks)} bookmarks "
                f"in {st.session_state.processing_time:.2f}ms"
            )

            if st.session_state.failed_bookmarks:
                st.error(f"Failed to process {len(st.session_state.failed_bookmarks)} bookmarks")

            st.subheader("Processed Bookmarks")
            for bookmark in st.session_state.processed_bookmarks:
                with st.expander(bookmark["title"]):
                    st.write("**Tags:**", ", ".join(bookmark["tags"]))
                    if bookmark["summary"]:
                        st.write("**Summary:**", bookmark["summary"])


if __name__ == "__main__":
    main()
