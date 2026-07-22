import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict
from urllib.parse import urlparse

from .errors import ApiError


class Client:
    """Makes HTTP requests to LLM APIs and handles retries with exponential backoff."""

    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder: Any) -> None:
        """Initialize client with a PromptBuilder instance."""
        self.builder = builder

    def call(self, max_output_tokens: int = 1024) -> Dict[str, Any]:
        """
        POST the payload to the API endpoint and return the parsed JSON response.

        Retries on transient errors and retryable HTTP status codes using exponential backoff.
        Raises ApiError on non-2xx response after retries exhausted, or on non-retryable errors.

        Args:
            max_output_tokens: Maximum tokens in response (default: 1024)

        Returns:
            Parsed JSON response from API as dict

        Raises:
            ApiError: On API failure after retries exhausted
        """
        url = self.builder.url()
        headers = self.builder.headers()
        payload = self.builder.to_api_payload(max_output_tokens=max_output_tokens)
        body = json.dumps(payload, default=str)

        parsed_url = urlparse(url)
        use_ssl = parsed_url.scheme == "https"

        ssl_context = ssl.create_default_context() if use_ssl else None

        attempts = 0

        while True:
            attempts += 1

            try:
                req = urllib.request.Request(
                    url,
                    data=body.encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                if ssl_context:
                    response = urllib.request.urlopen(req, context=ssl_context)
                else:
                    response = urllib.request.urlopen(req)

                status_code = response.status
                response_body = response.read().decode("utf-8")
                response.close()

                # Success (2xx)
                if 200 <= status_code < 300:
                    return json.loads(response_body)

                # Non-2xx response — check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue

                # Non-2xx, non-retryable — raise
                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                )

            except urllib.error.HTTPError as e:
                # HTTPError has status code and body
                status_code = e.code
                response_body = e.read().decode("utf-8")

                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue

                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                ) from e

            except (
                urllib.error.URLError,
                ssl.SSLError,
                TimeoutError,
                ConnectionError,
                BrokenPipeError,
                OSError,
            ) as e:
                # Transient error — retry if attempts remain
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    ) from e

                time.sleep(self._retry_delay(attempts))
                continue

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        """Calculate exponential backoff delay: 0.5s, 1s, 2s, 4s, ...

        Args:
            attempt: Attempt number (1-indexed)

        Returns:
            Delay in seconds as float
        """
        return Client.BASE_RETRY_DELAY * (2 ** (attempt - 1))
