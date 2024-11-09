import logging
import os
from datetime import datetime

import keybert
import keybert.llm
import openai
import requests
from dotenv import load_dotenv
from markdownify import markdownify
from raindropiopy import API, Collection, CollectionRef, Raindrop, RaindropType
from slugify import slugify

load_dotenv()


# Setup logging
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# Create handlers
all_logs_handler = logging.FileHandler(f"{log_dir}/raindrop_all_{timestamp}.log")
error_logs_handler = logging.FileHandler(f"{log_dir}/raindrop_errors_{timestamp}.log")
console_handler = logging.StreamHandler()

# Configure handlers
all_logs_handler.setLevel(logging.DEBUG)
error_logs_handler.setLevel(logging.ERROR)
console_handler.setLevel(logging.INFO)

# Create formatters and add it to handlers
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
all_logs_handler.setFormatter(log_format)
error_logs_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Get logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add handlers to the logger
logger.addHandler(all_logs_handler)
logger.addHandler(error_logs_handler)
logger.addHandler(console_handler)

client = openai.OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
)

llm = keybert.llm.OpenAI(client, model="gpt-4o-mini-2024-07-18", chat=True)
key_llm_model = keybert.KeyLLM(llm)
key_bert_model = keybert.KeyBERT(llm=key_llm_model)


def extract_keywords(text: str) -> list[str]:
    """Extract keywords from the text."""
    if len(text.split(" ")) > 1000:
        text = " ".join(text.split(" ")[:1000])
    keywords = key_bert_model.extract_keywords(text, keyphrase_ngram_range=(1, 2))
    if isinstance(keywords, list):
        keywords = keywords[0]

    keywords = [slugify(keyword) for keyword in keywords]
    return keywords


with API(os.environ["RAINDROP_TOKEN"]) as api:
    logger.info("Starting processing of unsorted Raindrop bookmarks")
    counter = 0
    for item in Raindrop.search(api, collection=CollectionRef.Unsorted):
        logger.debug(f"Processing item: {item.title}")

        if "_classified" in item.tags:
            logger.debug(f"Skipping already classified item: {item.title}")
            continue

        text = ""
        if item.type == RaindropType.link:
            counter += 1
            logger.info(f"Processing link {counter}: {item.title}")
            response = None
            try:
                logger.debug(f"Fetching content from: {item.link}")
                response = requests.get(item.link)
            except Exception as e:
                logger.error(f"Error fetching {item.link}: {e}")
                continue

            if response.status_code == requests.codes.ok:
                logger.info(f"Successfully fetched content from {item.link}")
                text = markdownify(response.text, strip=["a"])
        elif item.type == RaindropType.article:
            logger.info(f"Processing text {counter}: {item.title}")
            print(item.excerpt)
            text = item.excerpt

        if text == "":
            logger.error(f"No text found for {item.title}")
            continue

        try:
            logger.debug("Extracting keywords from content")
            keywords = extract_keywords(text)
            logger.info(f"Extracted keywords: {keywords}")

            logger.debug(f"Updating raindrop with new tags: {keywords}")
            raindrop = item.update(
                api,
                id=item.id,
                tags=item.tags + keywords + ["_classified"],
            )
            logger.info(f"Successfully updated raindrop: {item.title}")
        except Exception as e:
            logger.error(f"Error updating {item.title}: {e}", exc_info=True)

    logger.info(f"Processing completed. Total links processed: {counter}")
