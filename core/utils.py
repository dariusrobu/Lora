# core/utils.py
import asyncio
import functools
import logging
import random
from typing import Callable, Any

logger = logging.getLogger("core.utils")

def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """
    Decorator that implements exponential backoff for async functions.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Final attempt for {func.__name__} failed: {e}. "
                            f"Total attempts: {max_attempts}"
                        )
                        raise last_exception
                    
                    # Exponential backoff with jitter
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 0.1)
                    logger.warning(
                        f"Attempt {attempt + 1} for {func.__name__} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            return await func(*args, **kwargs)  # Should not reach here
        return wrapper
    return decorator
