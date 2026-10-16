"""Domain errors, mapped to HTTP responses by the API layer."""


class DomainError(Exception):
    """A rule violation: `status` is the HTTP status, `detail` a stable code."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
