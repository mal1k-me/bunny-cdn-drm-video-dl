import locale
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, cast

import ua_generator
import ua_generator.data
from ua_generator.data import T_BROWSERS, T_PLATFORMS

logger = logging.getLogger(__name__)


@dataclass
class BunnyHeaders:
    """
    Manages HTTP headers for Bunny CDN interactions.

    Generates a random User-Agent and Accept-Language header on initialization
    to mimic a real browser session.

    :param referer: The referer URL (website domain) where the video is embedded.
    :type referer: str
    :param embed_url: The embed URL of the video player.
    :type embed_url: str
    :param server_id: The server ID extracted from the embed page (optional).
    :type server_id: str
    """

    referer: str
    embed_url: str
    server_id: str = ""
    _ua_headers: Dict[str, str] = field(init=False)
    _accept_language: str = field(init=False)

    def __post_init__(self) -> None:
        """
        Initialize dynamic headers after object creation.

        Selects a random platform and browser, generates a User-Agent string
        with Client Hints, and selects a random locale for the Accept-Language header.
        """
        # Randomly select platform and browser from available options found in the library
        platform = random.choice(ua_generator.data.PLATFORMS)
        browser = random.choice(ua_generator.data.BROWSERS)

        logger.debug(f"Generating headers for platform: {platform}, browser: {browser}")

        # Generate dynamic user agent
        ua = ua_generator.generate(
            platform=cast(T_PLATFORMS, platform), browser=cast(T_BROWSERS, browser)
        )
        self._ua_headers = ua.headers.get()
        logger.debug(f"Generated User-Agent: {self._ua_headers.get('user-agent')}")

        # Generate random accept-language
        # Dynamically fetch available locales from system
        available_locales = [
            k.replace("_", "-")
            for k in locale.locale_alias.keys()
            if len(k) == 5 and k[2] == "_"
        ]

        if available_locales:
            raw_locale = random.choice(available_locales)
            # Format as lang-COUNTRY (e.g., en-US)
            lang, country = raw_locale.split("-")
            primary = f"{lang.lower()}-{country.upper()}"
        else:
            primary = "en-US"

        short = primary.split("-")[0]
        self._accept_language = f"{primary},{short};q=0.9"
        logger.debug(f"Generated Accept-Language: {self._accept_language}")

    @property
    def user_agent(self) -> Dict[str, str]:
        """
        Get the generated User-Agent and Client Hints headers.

        :return: Dictionary containing 'user-agent', 'sec-ch-ua', etc.
        :rtype: Dict[str, str]
        """
        return self._ua_headers

    @property
    def embed(self) -> Dict[str, str]:
        """
        Get headers for the embed page request.

        :return: Headers required to fetch the initial embed HTML.
        :rtype: Dict[str, str]
        """
        return {
            "authority": "iframe.mediadelivery.net",
            "accept": "*/*",
            "accept-language": self._accept_language,
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": self.referer,
            "sec-fetch-dest": "iframe",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "cross-site",
            "upgrade-insecure-requests": "1",
        }

    @property
    def ping_activate(self) -> Dict[str, str]:
        """
        Get headers for ping and activate requests.

        Includes the dynamic 'authority' header if server_id is set.

        :return: Headers for the DRM handshake requests.
        :rtype: Dict[str, str]
        """
        headers = {
            "accept": "*/*",
            "accept-language": self._accept_language,
            "cache-control": "no-cache",
            "origin": "https://iframe.mediadelivery.net",
            "pragma": "no-cache",
            "referer": "https://iframe.mediadelivery.net/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
        if self.server_id:
            headers["authority"] = f"video-{self.server_id}.mediadelivery.net"
        return headers

    @property
    def playlist(self) -> Dict[str, str]:
        """
        Get headers for playlist requests.

        :return: Headers for fetching the HLS playlist (.m3u8).
        :rtype: Dict[str, str]
        """
        return {
            "authority": "iframe.mediadelivery.net",
            "accept": "*/*",
            "accept-language": self._accept_language,
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": self.embed_url,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
