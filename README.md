# Raindrop Bookmark Classifier

This project provides a script to automatically classify bookmarks saved in [Raindrop.io](https://raindrop.io/) using keyword extraction. It leverages the [KeyBERT](https://github.com/MaartenGr/KeyBERT) library for keyword extraction, along with the [raindropiopy](https://github.com/PBorocz/raindrop-io-py) API wrapper for managing bookmarks.

## Features
- Extracts keywords from unsorted bookmarks on Raindrop.io using KeyBERT and OpenAI language models.
- Tags bookmarks based on extracted keywords.
- Logs detailed information about the processing of each bookmark.

## Prerequisites

- Python 3.8+
- [Raindrop.io account and API token](https://app.raindrop.io/settings/integrations).
- [OpenAI API key](https://platform.openai.com/account/api-keys).

## Installation

1. Clone this repository.
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with your OpenAI and Raindrop.io API keys:
   ```plaintext
   OPENAI_API_KEY=your_openai_api_key
   RAINDROP_TOKEN=your_raindrop_api_token
   OPENAI_MODEL=your_openai_model
   ```

## Usage

Run the script with the following command:
```bash
python raindrop_classifier.py
```

### Using Docker

You can also run the script using Docker:

1. Build the Docker image:
   ```bash
   docker build -t raindrop-extractor .
   ```

2. Run the container:
   ```bash
   docker run -v $(pwd)/logs:/app/logs --env-file .env raindrop-extractor
   ```

This will mount the local `logs` directory to the container and use the environment variables from your `.env` file.

Alternatively, you can use the provided bash script:
```bash
./build_and_run_docker.bash
```



## Code Overview

### Main Functions

1. **`extract_keywords`**: Extracts keywords from bookmark content with KeyBERT. Limits input length for performance.

2. **`setup_logging`**: Configures logging for debugging and error tracking. Logs are saved in a `logs` directory with timestamped files.

3. **`initialize_keyword_extractor`**: Sets up the KeyBERT model using OpenAI’s language model as a backend.

4. **`process_raindrop_items`**: Main function to process all unsorted bookmarks in Raindrop.io. It skips already classified bookmarks (those with `_classified` tag).

5. **`get_item_text`**: Fetches text content from Raindrop.io bookmarks. For link-type bookmarks, it fetches the page content, while for articles, it retrieves the saved excerpt.

6. **`process_single_item`**: Extracts keywords from an individual bookmark and updates it with keyword-based tags.

7. **`main`**: Loads environment variables, initializes the API and KeyBERT model, and starts the bookmark processing.

### Logging

The script logs each step, including:
- Successful retrieval of bookmark content.
- Errors during processing or updating bookmarks.
- Summary of processed bookmarks.

## Example Log Entry
```
2023-10-18 12:00:00 - INFO - Starting processing of unsorted Raindrop bookmarks
2023-10-18 12:00:05 - INFO - Successfully fetched content from https://example.com
2023-10-18 12:00:06 - INFO - Extracted keywords: ['machine-learning', 'ai-research']
2023-10-18 12:00:07 - INFO - Successfully updated raindrop: AI in 2023
2023-10-18 12:05:00 - INFO - Processing completed. Total links processed: 10
```

## Dependencies

- **KeyBERT**: Keyword extraction.
- **Raindropiopy**: API wrapper for Raindrop.io interactions.
- **dotenv**: For loading environment variables.
- **markdownify**: Converts HTML content into Markdown.
- **slugify**: Formats keywords into slug-friendly tags.
- **OpenAI**: Language model backend for KeyBERT.

## Contributing

If you wish to contribute, please fork the repository, create a feature branch, and submit a pull request.

## License

This project is licensed under the MIT License.

## Acknowledgments

- [KeyBERT](https://github.com/MaartenGr/KeyBERT) for keyword extraction.
- [raindropiopy](https://github.com/PBorocz/raindrop-io-py) for interacting with the Raindrop.io API. 

---

Happy tagging! If you run into issues, feel free to open an issue or reach out.