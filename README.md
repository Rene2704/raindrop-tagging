# Raindrop Bookmark Processor

A web application for automatically processing Raindrop.io bookmarks with tag extraction and summarization.

## Features

- Automatic tag extraction using KeyBERT
- Summary generation using Anthropic's Claude API
- Modern web interface built with Streamlit
- Command-line interface for batch processing
- Support for various bookmark types (links, articles, videos)
- Real-time processing status and progress tracking
- Option to update bookmarks directly in Raindrop.io

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

### Starting the Application

1. Start the backend server:
   ```bash
   poetry run uvicorn raindrop_information_extaction.api:app --reload
   ```
   The API will be available at http://localhost:8000

2. Start the frontend (in a new terminal):
   ```bash
   poetry run raindrop-web
   ```
   Or alternatively:
   ```bash
   poetry run streamlit run raindrop_information_extaction/frontend.py
   ```
   The web interface will be available at http://localhost:8501

### Web Interface

Use the web interface to:
- Select individual bookmarks to process
- Configure processing options:
  - Tag extraction
  - Summary generation
  - Raindrop.io updates
- View real-time processing results
- See processing statistics
- Monitor processing logs

### Command Line Interface

Run the CLI tool:
```bash
poetry run raindrop-process --help
```

CLI Options:
- `--tags/--no-tags`: Enable/disable tag extraction
- `--summary/--no-summary`: Enable/disable summary generation
- `--update/--no-update`: Enable/disable Raindrop.io updates

### API Documentation

Once the backend is running, view the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

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

1. Build the Docker image:
   ```bash
   docker build -t raindrop-processor .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 -p 8501:8501 --env-file .env raindrop-processor
   ```

   This will start both:
   - API server at http://localhost:8000
   - Web interface at http://localhost:8501

3. View logs:
   ```bash
   docker logs -f raindrop-processor
   ```

4. Stop the container:
   ```bash
   docker stop raindrop-processor
   ```

Note: Make sure your `.env` file is present in the same directory when running the container.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.