"""Module for processing YouTube videos saved in Raindrop.io.

This module provides functionality to:
1. Extract transcripts from YouTube videos saved in Raindrop.io
2. Generate summaries of the video content using Anthropic's Claude API
3. Update the Raindrop.io bookmarks with the generated summaries
"""

import re
from typing import Optional

import anthropic
from raindropiopy import API, Raindrop, RaindropType
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

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
    """Extract the video ID from a YouTube Shorts URL.

    Args:
        link: The YouTube Shorts URL

    Returns:
        The video ID if found, None otherwise
    """
    match = re.search(r"shorts/([a-zA-Z0-9_-]+)", link)
    return match.group(1) if match else None


def extract_youtube_id(link: str) -> Optional[str]:
    """Extract the video ID from a standard YouTube video URL.

    Args:
        link: The YouTube video URL

    Returns:
        The video ID if found, None otherwise
    """
    match = re.search(
        r"(?:youtube\.com/(?:embed/|v/|watch\?v=|watch\?.+&v=)|youtu\.be/)([a-zA-Z0-9_-]{11})",
        link,
    )
    return match.group(1) if match else None


def extract_video_id(youtube_url: str) -> Optional[str]:
    """Extract video ID from any YouTube URL (both standard videos and shorts).

    Args:
        youtube_url: The YouTube URL (either standard video or shorts)

    Returns:
        The video ID if found, None otherwise
    """
    if "shorts/" in youtube_url:
        return extract_youtube_short_id(youtube_url)
    return extract_youtube_id(youtube_url)


def get_transcript(video_id: str) -> str:
    """Get the transcript text for a YouTube video.

    This function attempts to get the transcript in the following order:
    1. Manually created English transcripts (en-US, en-GB)
    2. Auto-generated English transcript (en)

    Args:
        video_id: The YouTube video ID

    Returns:
        The transcript text as a single string with spaces between segments

    Raises:
        NoTranscriptFound: If no suitable transcript is available
    """
    formatter = TextFormatter()

    # Try to get manually created English transcripts first
    manual_langs = ["en-US", "en-GB"]
    for lang in manual_langs:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            return formatter.format_transcript(transcript).replace("\n", " ")
        except Exception:
            continue

    # If no manual transcript, try auto-generated
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return formatter.format_transcript(transcript).replace("\n", " ")
    except Exception as e:
        # Get available transcript languages for better error message
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
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
                error_msg += (
                    f"Available manual transcripts: {', '.join(available_langs)}\n"
                )
            if auto_langs:
                error_msg += (
                    f"Available auto-generated transcripts: {', '.join(auto_langs)}"
                )

            raise ValueError(error_msg) from e
        except Exception:
            raise ValueError(f"No transcript available for video {video_id}")


def generate_paper_summary(
    text: str,
    anthropic_client: anthropic.Anthropic,
    model: str = "claude-3-haiku-20240307",
) -> str:
    """Generate a comprehensive summary of the text using Anthropic's Claude API.

    Args:
        text: The text to summarize
        anthropic_client: Initialized Anthropic client
        model: The Claude model to use

    Returns:
        A markdown-formatted summary combining core message, summary, and key ideas
    """
    if not isinstance(text, str) or len(text) < 10:
        return ""

    # Generate ideas
    ideas_message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        system=IDEAS_PROMPT,
        messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
    )
    ideas_text = ideas_message.content[0].text if ideas_message.content else ""

    # Generate summary
    summary_message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
    )
    summary_text = summary_message.content[0].text if summary_message.content else ""

    # Generate core message
    core_message = anthropic_client.messages.create(
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
    )
    core_text = core_message.content[0].text if core_message.content else ""

    return f"""
# Core Message

{core_text}

# Summary

{summary_text}

# Key Ideas

{ideas_text}
    """


def process_youtube_videos(
    api: API,
    anthropic_client: anthropic.Anthropic,
    model: str = "claude-3-haiku-20240307",
) -> None:
    """Process YouTube videos saved in Raindrop.io.

    This function:
    1. Searches for YouTube videos in Raindrop.io
    2. Extracts their transcripts
    3. Generates summaries using Claude
    4. Updates the Raindrop.io bookmarks with the summaries

    Args:
        api: Initialized Raindrop.io API client
        anthropic_client: Initialized Anthropic client
        model: The Claude model to use for summarization
    """
    youtube_videos = [
        video
        for video in Raindrop.search(api, search="youtube.com")
        if video.type == RaindropType.video
    ]

    for video in youtube_videos:
        if "_video_summarized" in video.tags:
            continue

        try:
            video_id = extract_video_id(video.link)
            if not video_id:
                print(f"Could not extract video ID from {video.link}")
                continue

            try:
                transcript_text = get_transcript(video_id)
            except ValueError as e:
                print(f"Skipping video {video.title}: {str(e)}")
                continue

            description = generate_paper_summary(
                transcript_text, anthropic_client, model
            )
            print(description)
            Raindrop.update(
                api,
                id=video.id,
                note=description,
                tags=video.tags + ["_video_summarized"],
            )
            print(f"Successfully processed video: {video.title}")

        except Exception as e:
            print(f"Error processing video {video.id}: {e}")


def main():
    """Main entry point for the script.

    Requires the following environment variables:
    - RAINDROP_TOKEN: Your Raindrop.io API token
    - ANTHROPIC_API_KEY: Your Anthropic API key
    """
    import os

    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Initialize clients
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    with API(os.getenv("RAINDROP_TOKEN")) as api:
        process_youtube_videos(api, anthropic_client)


if __name__ == "__main__":
    main()
