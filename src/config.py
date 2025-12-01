import re
from dataclasses import dataclass
from typing import Optional

from src.exceptions import ConfigurationError


@dataclass
class DownloadConfig:
    """
    Configuration data class for the video download.

    Holds all necessary parameters and performs validation on initialization.

    :param referer: The referer URL (website domain) where the video is embedded.
    :type referer: str
    :param embed_url: The embed URL of the video player.
    :type embed_url: str
    :param name: Optional override for the output filename (without extension).
    :type name: Optional[str]
    :param path: Optional override for the download directory path.
    :type path: Optional[str]
    :param interactive: Enable interactive mode for resolution selection.
    :type interactive: bool
    :param resolution: Optional resolution to select (e.g. "1080", "720") or regex pattern.
    :type resolution: Optional[str]
    :param log_file: Optional path to a log file.
    :type log_file: Optional[str]
    """

    referer: str
    embed_url: str
    name: Optional[str] = None
    path: Optional[str] = None
    interactive: bool = False
    resolution: Optional[str] = None
    log_file: Optional[str] = None

    def __post_init__(self) -> None:
        """
        Validate configuration after initialization.

        Ensures required fields are present and the referer URL is valid.
        Appends a trailing slash to the referer if missing.

        :raises ConfigurationError: If referer or embed_url are missing, or if referer format is invalid.
        """
        if not self.referer or not self.embed_url:
            raise ConfigurationError("Referer and Embed URL are required.")

        # Ensure referer ends with a slash for consistency
        if not self.referer.endswith("/"):
            self.referer += "/"

        # Validate referer format (must be a valid http/https URL with domain)
        if not re.match(r"^https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}/", self.referer):
            raise ConfigurationError(
                f"Invalid referer URL: {self.referer}. Must be http(s)://domain.tld/"
            )
