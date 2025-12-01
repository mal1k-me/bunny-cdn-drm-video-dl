class BunnyVideoError(Exception):
    """
    Base exception for Bunny CDN Video Downloader.

    All custom exceptions in this project inherit from this class.
    """

    pass


class ConfigurationError(BunnyVideoError):
    """
    Raised when configuration is invalid or missing.

    This includes missing required arguments or malformed URLs.
    """

    pass


class NetworkError(BunnyVideoError):
    """
    Raised when network requests fail.

    Wraps requests.RequestException and other network-related errors.
    """

    pass


class ExtractionError(BunnyVideoError):
    """
    Raised when parsing or extracting data fails.

    Occurs when regex matches fail to find expected data in the embed page.
    """

    pass


class PlaylistError(BunnyVideoError):
    """
    Raised when playlist operations fail.

    Occurs when no resolutions are found or playlist fetching fails.
    """

    pass
