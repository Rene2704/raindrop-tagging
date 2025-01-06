"""Module for processing YouTube videos saved in Raindrop.io."""

import logging
import re
from typing import Optional

import anthropic
from raindropiopy import API, Raindrop, RaindropType
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from .api_utils import safe_api_call

# Configure logging
logger = logging.getLogger(__name__)

# Constants for prompts
CORE_MESSAGE_PROMPT = """
# IDENTITY and PURPOSE

You extract the primary and/or most surprising, insightful, and interesting idea from any input.
Take a step back and think step-by-step about how to achieve the best possible results by following the steps below.

# STEPS

- Fully digest the content provided.
- Extract the most important idea from the content.
- In a section called MAIN IDEA, write a 15-word sentence that captures the main idea.
- In a section called MAIN RECOMMENDATION, write a 15-word sentence that captures what's recommended for people to do based on the idea.

# OUTPUT INSTRUCTIONS

- Only output Markdown.
- Do not give warnings or notes; only output the requested sections.
- Do not repeat ideas, quotes, facts, or resources.
- Do not start items with the same opening words.
- Ensure you follow ALL these instructions when creating your output.

# INPUT

INPUT:
"""

IDEAS_PROMPT = """
# IDENTITY and PURPOSE
You are an advanced AI with a 2,128 IQ and you are an expert in understanding any input and extracting the most important ideas from it.

# STEPS
1. Spend 319 hours fully digesting the input provided.
2. Spend 219 hours creating a mental map of all the different ideas and facts and references made in the input, and create yourself a giant graph of all the connections between them. E.g., Idea1 --> Is the Parent of --> Idea2. Concept3 --> Came from --> Socrates. Etc. And do that for every single thing mentioned in the input.
3. Write that graph down on a giant virtual whiteboard in your mind.
4. Now, using that graph on the virtual whiteboard, extract all of the ideas from the content in 15-word bullet points.

# OUTPUT
- Output the FULL list of ideas from the content in a section called IDEAS

# EXAMPLE OUTPUT
IDEAS

- The purpose of life is to find meaning and fulfillment in our existence.
- Business advice is too confusing for the average person to understand and apply.
- (continued)

END EXAMPLE OUTPUT

# OUTPUT INSTRUCTIONS
- Only output Markdown.
- Do not give warnings or notes; only output the requested sections.
- Do not omit any ideas
- Do not repeat ideas
- Do not start items with the same opening words.
- Ensure you follow ALL these instructions when creating your output.

# INPUT

INPUT:
"""

SUMMARY_PROMPT = """
# IDENTITY and PURPOSE
You are an expert content summarizer. You take content in and output a Markdown formatted summary using the format below.
Take a deep breath and think step by step about how to best accomplish this goal using the following steps.

# OUTPUT SECTIONS
- Combine all of your understanding of the content into a single, 20-word sentence in a section called ONE SENTENCE SUMMARY:.
- Output the 10 most important points of the content as a list with no more than 15 words per point into a section called MAIN POINTS:.
- Output a list of the 5 best takeaways from the content in a section called TAKEAWAYS:.

# OUTPUT INSTRUCTIONS
- Create the output using the formatting above.
- You only output human readable Markdown.
- Output numbered lists, not bullets.
- Do not output warnings or notes—just the requested sections.
- Do not repeat items in the output sections.
- Do not start items with the same opening words.

# INPUT:

INPUT:
"""


def extract_youtube_short_id(link: str) -> Optional[str]:
    """Extract the video ID from a YouTube Shorts URL."""
    logger.info(f"Extracting video ID from YouTube Shorts URL: {link}")
    match = re.search(r"shorts/([a-zA-Z0-9_-]+)", link)
    if match:
        video_id = match.group(1)
        logger.info(f"Successfully extracted video ID: {video_id}")
        return video_id
    logger.error("Failed to extract video ID from YouTube Shorts URL")
    return None


def extract_youtube_id(link: str) -> Optional[str]:
    """Extract the video ID from a standard YouTube video URL."""
    logger.info(f"Extracting video ID from standard YouTube URL: {link}")
    match = re.search(
        r"(?:youtube\.com/(?:embed/|v/|watch\?v=|watch\?.+&v=)|youtu\.be/)([a-zA-Z0-9_-]{11})",
        link,
    )
    if match:
        video_id = match.group(1)
        logger.info(f"Successfully extracted video ID: {video_id}")
        return video_id
    logger.error("Failed to extract video ID from standard YouTube URL")
    return None


def extract_video_id(youtube_url: str) -> Optional[str]:
    """Extract video ID from any YouTube URL (both standard videos and shorts)."""
    logger.info(f"Attempting to extract video ID from URL: {youtube_url}")
    if "shorts/" in youtube_url:
        logger.info("Detected YouTube Shorts URL")
        return extract_youtube_short_id(youtube_url)
    logger.info("Detected standard YouTube URL")
    return extract_youtube_id(youtube_url)


def get_transcript(video_id: str) -> str:
    """Get the transcript text for a YouTube video."""
    logger.info(f"Fetching transcript for video ID: {video_id}")
    formatter = TextFormatter()

    # Try to get manually created English transcripts first
    manual_langs = ["en-US", "en-GB"]
    for lang in manual_langs:
        try:
            logger.info(f"Attempting to fetch manual transcript in {lang}")
            transcript = safe_api_call(
                YouTubeTranscriptApi.get_transcript,
                video_id,
                languages=[lang],
                max_retries=3,
                logger=logger,
            )
            if transcript:
                logger.info(f"Successfully found manual transcript in {lang}")
                return formatter.format_transcript(transcript).replace("\n", " ")
            logger.info(f"No manual transcript found in {lang}")
        except Exception:
            logger.info(f"No manual transcript found in {lang}")
            continue

    # If no manual transcript, try auto-generated
    try:
        logger.info("Attempting to fetch auto-generated English transcript")
        transcript = safe_api_call(
            YouTubeTranscriptApi.get_transcript,
            video_id,
            languages=["en"],
            max_retries=3,
            logger=logger,
        )
        if transcript:
            logger.info("Successfully found auto-generated transcript")
            return formatter.format_transcript(transcript).replace("\n", " ")
    except Exception as e:
        # Get available transcript languages for better error message
        try:
            logger.info("Fetching list of available transcripts")
            transcript_list = safe_api_call(
                YouTubeTranscriptApi.list_transcripts,
                video_id,
                max_retries=3,
                logger=logger,
            )
            if transcript_list:
                available_langs = [
                    f"{t.language_code} ({t.language})"
                    for t in transcript_list._manually_created_transcripts.values()
                ]
                auto_langs = [
                    f"{t.language_code} ({t.language})"
                    for t in transcript_list._generated_transcripts.values()
                ]

                error_msg = f"No English transcript found for video {video_id}.\n"
                if available_langs:
                    error_msg += f"Available manual transcripts: {', '.join(available_langs)}\n"
                if auto_langs:
                    error_msg += f"Available auto-generated transcripts: {', '.join(auto_langs)}"

                logger.error(error_msg)
                raise ValueError(error_msg) from e
        except Exception:
            error_msg = f"No transcript available for video {video_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)


def generate_paper_summary(
    text: str,
    anthropic_client: anthropic.Anthropic,
    model: str = "claude-3-haiku-20240307",
) -> str:
    """Generate a comprehensive summary of the text using Anthropic's Claude API."""
    if not isinstance(text, str) or len(text) < 10:
        logger.error("Invalid input text for summary generation")
        return ""

    logger.info("Generating ideas using Claude")
    try:
        ideas_message = safe_api_call(
            anthropic_client.messages.create,
            model=model,
            max_tokens=1024,
            temperature=0,
            system=IDEAS_PROMPT,
            messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
            max_retries=3,
            logger=logger,
        )
        ideas_text = (
            ideas_message.content[0].text if ideas_message and ideas_message.content else ""
        )
        logger.info("Successfully generated ideas")
    except Exception as e:
        logger.error(f"Error generating ideas: {e}")
        ideas_text = ""

    logger.info("Generating summary using Claude")
    try:
        summary_message = safe_api_call(
            anthropic_client.messages.create,
            model=model,
            max_tokens=1024,
            temperature=0,
            system=SUMMARY_PROMPT,
            messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
            max_retries=3,
            logger=logger,
        )
        summary_text = (
            summary_message.content[0].text if summary_message and summary_message.content else ""
        )
        logger.info("Successfully generated summary")
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        summary_text = ""

    logger.info("Generating core message using Claude")
    try:
        core_message = safe_api_call(
            anthropic_client.messages.create,
            model=model,
            max_tokens=1024,
            temperature=0,
            system=CORE_MESSAGE_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": summary_text + ideas_text}],
                }
            ],
            max_retries=3,
            logger=logger,
        )
        core_text = core_message.content[0].text if core_message and core_message.content else ""
        logger.info("Successfully generated core message")
    except Exception as e:
        logger.error(f"Error generating core message: {e}")
        core_text = ""

    final_summary = f"""
# Core Message

{core_text}

# Summary

{summary_text}

# Key Ideas

{ideas_text}
    """
    logger.info("Successfully compiled complete summary")
    return final_summary


def process_youtube_videos(
    api: API,
    anthropic_client: anthropic.Anthropic,
    model: str = "claude-3-haiku-20240307",
) -> None:
    """Process YouTube videos saved in Raindrop.io."""
    logger.info("Starting YouTube video processing")
    try:

        def search_videos():
            return [
                video
                for video in Raindrop.search(api, search="youtube.com")
                if video.type == RaindropType.video
            ]

        youtube_videos = safe_api_call(search_videos, max_retries=5, logger=logger)
        if not youtube_videos:
            logger.error("Failed to fetch YouTube videos")
            return

        logger.info(f"Found {len(youtube_videos)} YouTube videos")

        for video in youtube_videos:
            if "_video_summarized" in video.tags:
                logger.info(f"Skipping already processed video: {video.title}")
                continue

            try:
                logger.info(f"Processing video: {video.title}")
                video_id = extract_video_id(video.link)
                if not video_id:
                    logger.error(f"Could not extract video ID from {video.link}")
                    continue

                try:
                    logger.info("Fetching video transcript")
                    transcript_text = get_transcript(video_id)
                except ValueError as e:
                    logger.error(f"Skipping video {video.title}: {str(e)}")
                    continue

                logger.info("Generating video summary")
                description = generate_paper_summary(transcript_text, anthropic_client, model)

                logger.info("Updating video in Raindrop")

                def update_video():
                    return Raindrop.update(
                        api,
                        id=video.id,
                        note=description,
                        tags=video.tags + ["_video_summarized"],
                    )

                if safe_api_call(update_video, max_retries=5, logger=logger):
                    logger.info(f"Successfully processed video: {video.title}")
                else:
                    logger.error(f"Failed to update video: {video.title}")

            except Exception as e:
                logger.error(f"Error processing video {video.id}: {e}")

        logger.info("YouTube video processing completed")

    except Exception as e:
        logger.error(f"Error in YouTube video processing: {e}")


def main():
    """Main entry point for the script."""
    logger.info("Starting YouTube video processing script")
    try:
        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv()
        logger.info("Environment variables loaded")

        # Initialize clients
        logger.info("Initializing Anthropic client")
        anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        logger.info("Processing videos")
        with API(os.environ["RAINDROP_TOKEN"]) as api:
            process_youtube_videos(api, anthropic_client)

        logger.info("Script completed successfully")

    except Exception as e:
        logger.error(f"Script failed: {e}")


if __name__ == "__main__":
    main()
