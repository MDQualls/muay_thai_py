class FetchError(Exception):
    """Raised when fetching fighter data from the Wikipedia or SportsDB API fails."""


class EnrichmentError(Exception):
    """Raised when Claude enrichment fails or returns unparseable output."""


class RenderError(Exception):
    """Raised when Playwright card rendering fails."""


class UploadError(Exception):
    """Raised when uploading a card to Cloudflare R2 fails."""


class PublishError(Exception):
    """Raised when posting to Instagram via the Meta Graph API fails."""


class DatabaseError(Exception):
    """Raised when a database read or write operation fails."""
