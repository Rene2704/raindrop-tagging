"""Utility functions for handling API calls with rate limiting and retries."""

import logging
import time
from typing import Any, Callable, Optional, TypeVar

import requests

T = TypeVar("T")  # Generic type for function return value


class RateLimitError(Exception):
    """Exception raised when API rate limit is hit."""

    def __init__(self, reset_time: int, message: str = "Rate limit exceeded"):
        self.reset_time = reset_time
        self.message = message
        super().__init__(self.message)


def handle_rate_limit(response: requests.Response, logger: logging.Logger) -> None:
    """Handle rate limit response from API.

    Args:
        response: The response object containing rate limit headers
        logger: Logger instance for logging messages
    """
    if response.status_code == 429:
        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
        current_time = int(time.time())
        wait_time = max(reset_time - current_time, 1)  # At least 1 second
        logger.warning(f"Rate limit hit. Waiting {wait_time} seconds before retrying...")
        time.sleep(wait_time)


def exponential_backoff(attempt: int, max_wait: int = 32) -> None:
    """Implement exponential backoff for retries.

    Args:
        attempt: Current attempt number (0-based)
        max_wait: Maximum wait time in seconds
    """
    wait_time = min(2**attempt, max_wait)
    time.sleep(wait_time)


def safe_api_call(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 5,
    logger: logging.Logger,
    **kwargs: Any,
) -> Optional[T]:
    """Execute an API call with retry logic and rate limit handling.

    Args:
        func: Function to call
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        logger: Logger instance for logging messages
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call, or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            return result
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, "status_code") and e.response.status_code == 429:
                handle_rate_limit(e.response, logger)
                continue
            elif attempt == max_retries - 1:
                raise
            logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}). Retrying...")
            exponential_backoff(attempt)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"API call failed after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}). Retrying...")
            exponential_backoff(attempt)
    return None
