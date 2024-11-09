import logging
import os
from datetime import datetime

import keybert
import keybert.llm
import openai
import requests
from dotenv import load_dotenv
from markdownify import markdownify
from raindropiopy import API, CollectionRef, Raindrop, RaindropType
from slugify import slugify


def extract_keywords(text: str, key_bert_model: keybert.KeyBERT) -> list[str]:
    """Extract keywords from the text."""
    if len(text.split(" ")) > 1000:
        text = " ".join(text.split(" ")[:1000])
    keywords = key_bert_model.extract_keywords(text, keyphrase_ngram_range=(1, 2))
    if isinstance(keywords, list):
        keywords = keywords[0]

    keywords = [slugify(keyword) for keyword in keywords]
    return keywords


def setup_logging() -> logging.Logger:
    """Configure and return a logger with file and console handlers."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    handlers = [
        (logging.FileHandler(f"{log_dir}/raindrop_all_{timestamp}.log"), logging.DEBUG),
        (
            logging.FileHandler(f"{log_dir}/raindrop_errors_{timestamp}.log"),
            logging.ERROR,
        ),
        (logging.StreamHandler(), logging.INFO),
    ]

    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    for handler, level in handlers:
        handler.setLevel(level)
        handler.setFormatter(log_format)
        logger.addHandler(handler)

    return logger


def initialize_keyword_extractor(api_key: str, model: str) -> keybert.KeyBERT:
    """Initialize and return KeyBERT model with OpenAI configuration."""
    client = openai.OpenAI(api_key=api_key)
    llm = keybert.llm.OpenAI(client, model=model, chat=True)
    return keybert.KeyBERT(llm=keybert.KeyLLM(llm))


def process_raindrop_items(
    api: API, key_bert_model: keybert.KeyBERT, logger: logging.Logger
) -> None:
    """Process unsorted Raindrop bookmarks and add keyword-based tags."""
    logger.info("Starting processing of unsorted Raindrop bookmarks")
    counter = 0

    for item in Raindrop.search(api, collection=CollectionRef.Unsorted):
        logger.debug(f"Processing item: {item.title}")

        if "_classified" in item.tags:
            logger.debug(f"Skipping already classified item: {item.title}")
            continue

        text = get_item_text(item, logger)
        if not text:
            continue

        try:
            process_single_item(item, text, api, key_bert_model, logger)
        except Exception as e:
            logger.error(f"Error updating {item.title}: {e}", exc_info=True)
            continue

        counter += 1

    logger.info(f"Processing completed. Total links processed: {counter}")


def get_item_text(item: Raindrop, logger: logging.Logger) -> str:
    """Extract text content from a Raindrop item."""
    if item.type == RaindropType.link:
        logger.info(f"Processing link: {item.title}")
        try:
            response = requests.get(item.link)
            if response.status_code == requests.codes.ok:
                logger.info(f"Successfully fetched content from {item.link}")
                return markdownify(response.text, strip=["a"])
        except Exception as e:
            logger.error(f"Error fetching {item.link}: {e}")

    elif item.type == RaindropType.article:
        logger.info(f"Processing article: {item.title}")
        return item.excerpt

    logger.error(f"No text found for {item.title}")
    return ""


def process_single_item(
    item: Raindrop,
    text: str,
    api: API,
    key_bert_model: keybert.KeyBERT,
    logger: logging.Logger,
) -> None:
    """Process a single Raindrop item by extracting keywords and updating tags."""
    logger.debug("Extracting keywords from content")
    keywords = extract_keywords(text, key_bert_model)
    logger.info(f"Extracted keywords: {keywords}")

    logger.debug(f"Updating raindrop with new tags: {keywords}")
    item.update(
        api,
        id=item.id,
        tags=item.tags + keywords + ["_classified"],
    )
    logger.info(f"Successfully updated raindrop: {item.title}")


def main():
    """Main execution function."""
    load_dotenv()
    logger = setup_logging()
    key_bert_model = initialize_keyword_extractor(
        os.environ["OPENAI_API_KEY"], os.environ["OPENAI_MODEL"]
    )

    with API(os.environ["RAINDROP_TOKEN"]) as api:
        process_raindrop_items(api, key_bert_model, logger)


if __name__ == "__main__":
    main()
