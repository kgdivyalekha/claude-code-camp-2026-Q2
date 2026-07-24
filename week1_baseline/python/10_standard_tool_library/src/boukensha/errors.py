class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with an unsupported model."""
    pass


class ApiError(Exception):
    """Raised when an API request fails after retries are exhausted."""
    pass


class LoopError(Exception):
    """Reserved for future use — not currently raised anywhere."""
    pass
