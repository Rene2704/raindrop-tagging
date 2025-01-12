"""Command line interface for the Raindrop bookmark processor."""

import logging
import os
from datetime import datetime
from typing import List, Optional

import anthropic
import keybert
import typer
from dotenv import load_dotenv
from raindropiopy import API, CollectionRef, Raindrop
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from raindrop_information_extaction.processors import BookmarkProcessor

# Initialize Typer app
app = typer.Typer(
    name="raindrop-processor",
    help="Process Raindrop.io bookmarks with tag extraction and summarization.",
)

# Initialize console for rich output
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def init_processor() -> Optional[BookmarkProcessor]:
    """Initialize the bookmark processor with required clients."""
    try:
        # Load environment variables
        load_dotenv()

        # Check required environment variables
        required_vars = ["RAINDROP_TOKEN", "OPENAI_API_KEY", "OPENAI_MODEL", "ANTHROPIC_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            console.print(
                f"[red]Missing required environment variables: {', '.join(missing_vars)}[/]"
            )
            return None

        # Initialize clients
        key_bert_model = keybert.KeyBERT()
        claude_client = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Create processor
        return BookmarkProcessor(
            raindrop_token=os.getenv("RAINDROP_TOKEN"),
            key_bert_model=key_bert_model,
            claude_client=claude_client,
            logger=logger,
        )
    except Exception as e:
        console.print(f"[red]Error initializing processor: {e}[/]")
        return None


def get_unprocessed_bookmarks(api: API) -> List[str]:
    """Get IDs of unprocessed bookmarks."""
    try:
        bookmarks = []
        for bookmark in Raindrop.search(api):
            if "_processed" not in bookmark.tags:
                bookmarks.append(str(bookmark.id))
        return bookmarks
    except Exception as e:
        console.print(f"[red]Error fetching bookmarks: {e}[/]")
        return []


@app.command()
def process_all(
    extract_tags: bool = typer.Option(True, "--tags/--no-tags", help="Extract tags using KeyBERT"),
    generate_summary: bool = typer.Option(
        True, "--summary/--no-summary", help="Generate summaries using Claude"
    ),
    update_raindrop: bool = typer.Option(
        True, "--update/--no-update", help="Update bookmarks in Raindrop.io"
    ),
):
    """Process all unprocessed bookmarks in your Raindrop.io account."""
    processor = init_processor()
    if not processor:
        raise typer.Exit(code=1)

    with API(os.getenv("RAINDROP_TOKEN")) as api:
        # Get unprocessed bookmarks
        bookmark_ids = get_unprocessed_bookmarks(api)
        if not bookmark_ids:
            console.print("[yellow]No unprocessed bookmarks found.[/]")
            return

        console.print(f"[green]Found {len(bookmark_ids)} unprocessed bookmarks.[/]")

        # Process bookmarks with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing bookmarks...", total=len(bookmark_ids))

            processed_bookmarks, failed_bookmarks = processor.process_bookmarks(
                bookmark_ids=bookmark_ids,
                extract_tags=extract_tags,
                generate_summary=generate_summary,
                update_raindrop=update_raindrop,
            )
            progress.update(task, advance=1)

        # Print results
        console.print("\n[bold green]Processing completed![/]")
        console.print(f"Successfully processed: {len(processed_bookmarks)} bookmarks")
        console.print(f"Failed to process: {len(failed_bookmarks)} bookmarks")

        if failed_bookmarks:
            console.print("\n[yellow]Failed bookmark IDs:[/]")
            for bookmark_id in failed_bookmarks:
                console.print(f"- {bookmark_id}")


@app.command()
def process_bookmarks(
    bookmark_ids: List[str] = typer.Argument(..., help="List of bookmark IDs to process"),
    extract_tags: bool = typer.Option(True, "--tags/--no-tags", help="Extract tags using KeyBERT"),
    generate_summary: bool = typer.Option(
        True, "--summary/--no-summary", help="Generate summaries using Claude"
    ),
    update_raindrop: bool = typer.Option(
        True, "--update/--no-update", help="Update bookmarks in Raindrop.io"
    ),
):
    """Process specific bookmarks by their IDs."""
    processor = init_processor()
    if not processor:
        raise typer.Exit(code=1)

    console.print(f"[green]Processing {len(bookmark_ids)} bookmarks...[/]")

    # Process bookmarks with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing bookmarks...", total=len(bookmark_ids))

        processed_bookmarks, failed_bookmarks = processor.process_bookmarks(
            bookmark_ids=bookmark_ids,
            extract_tags=extract_tags,
            generate_summary=generate_summary,
            update_raindrop=update_raindrop,
        )
        progress.update(task, advance=1)

    # Print results
    console.print("\n[bold green]Processing completed![/]")
    console.print(f"Successfully processed: {len(processed_bookmarks)} bookmarks")
    console.print(f"Failed to process: {len(failed_bookmarks)} bookmarks")

    if failed_bookmarks:
        console.print("\n[yellow]Failed bookmark IDs:[/]")
        for bookmark_id in failed_bookmarks:
            console.print(f"- {bookmark_id}")


@app.command()
def list_unprocessed():
    """List all unprocessed bookmarks in your Raindrop.io account."""
    processor = init_processor()
    if not processor:
        raise typer.Exit(code=1)

    with API(os.getenv("RAINDROP_TOKEN")) as api:
        try:
            console.print("[green]Fetching unprocessed bookmarks...[/]")
            logger.info("Searching unsorted collection")
            bookmarks = list(Raindrop.search(api, collection=CollectionRef.Unsorted))
            for bookmark in bookmarks:
                if "_processed" not in bookmark.tags:
                    console.print(f"ID: {bookmark.id} - Title: {bookmark.title}")
        except Exception as e:
            console.print(f"[red]Error listing bookmarks: {e}[/]")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
