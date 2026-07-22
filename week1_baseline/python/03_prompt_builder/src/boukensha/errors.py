class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with an unsupported model."""
    pass
