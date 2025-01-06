# Raindrop Bookmark Processor

A web application for automatically processing Raindrop.io bookmarks with tag extraction and summarization.

## Features

- Automatic tag extraction using KeyBERT
- Summary generation using Anthropic's Claude API
- Modern web interface built with Streamlit
- RESTful API built with FastAPI
- Support for various bookmark types (links, articles, videos)
- Batch processing capabilities
- Real-time processing status and results

## Requirements

- Python 3.11 or higher
- Poetry for dependency management
- Raindrop.io API token
- OpenAI API key (for KeyBERT)
- Anthropic API key (for Claude)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/raindrop-labels.git
   cd raindrop-labels
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Create a `.env` file with your API keys:
   ```env
   RAINDROP_TOKEN=your_raindrop_token
   OPENAI_API_KEY=your_openai_key
   OPENAI_MODEL=gpt-4
   ANTHROPIC_API_KEY=your_anthropic_key
   ```

## Usage

1. Start the application:
   ```bash
   poetry run python -m raindrop_information_extaction.main
   ```

   This will start both the FastAPI backend server and the Streamlit frontend.

2. Open your browser:
   - Frontend: http://localhost:8501
   - API docs: http://localhost:8000/docs

3. Use the web interface to:
   - Select bookmarks to process
   - Configure processing options
   - View processing results
   - Monitor processing status

## API Endpoints

- `POST /process-bookmarks/`: Process a list of bookmarks
  ```json
  {
    "bookmark_ids": ["id1", "id2"],
    "update_raindrop": true,
    "extract_tags": true,
    "generate_summary": true
  }
  ```

- `GET /processing-history/`: Get processing history

## Development

1. Install development dependencies:
   ```bash
   poetry install --with dev
   ```

2. Run tests:
   ```bash
   poetry run pytest
   ```

3. Format code:
   ```bash
   poetry run black .
   poetry run isort .
   ```

4. Run linting:
   ```bash
   poetry run ruff check .
   ```

## Docker Support

Build and run with Docker:

```bash
docker build -t raindrop-processor .
docker run -p 8000:8000 -p 8501:8501 --env-file .env raindrop-processor
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.