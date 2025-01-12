import logging
import os
import subprocess
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_environment() -> bool:
    """Check if all required environment variables are set."""
    required_vars = ["RAINDROP_TOKEN", "OPENAI_API_KEY", "OPENAI_MODEL", "ANTHROPIC_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    return True


def start_api_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the FastAPI server."""
    logger.info(f"Starting FastAPI server at http://{host}:{port}")
    uvicorn.run(
        "raindrop_information_extaction.api:app",
        host=host,
        port=port,
        reload=True,
    )


def start_streamlit(port: int = 8501) -> None:
    """Start the Streamlit frontend."""
    logger.info(f"Starting Streamlit frontend at http://localhost:{port}")
    frontend_path = Path(__file__).parent / "frontend.py"
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(frontend_path)])


def main():
    """Main entry point for the application."""
    # Load environment variables
    load_dotenv()

    # Check environment
    if not check_environment():
        sys.exit(1)

    try:
        # Start Streamlit frontend
        start_streamlit()

        # Start FastAPI server
        start_api_server()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
