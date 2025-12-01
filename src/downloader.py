import logging
import re
import threading
import time
from hashlib import md5
from html import unescape
from pathlib import Path
from random import random
from urllib.parse import urlparse
from typing import Any, Dict, cast, TYPE_CHECKING

import requests
import yt_dlp

if TYPE_CHECKING:
    from yt_dlp import _Params

from src.config import DownloadConfig
from src.headers import BunnyHeaders
from src.exceptions import (
    ConfigurationError,
    ExtractionError,
    NetworkError,
    PlaylistError,
)

logger = logging.getLogger(__name__)


class BunnyVideoDRM:
    """
    Main downloader class for Bunny CDN DRM-protected videos.

    Handles the entire process of:
    1. Parsing the embed page to extract secrets and IDs.
    2. Authenticating with the DRM server (ping/activate).
    3. Maintaining a session with background pings.
    4. Downloading the video using yt-dlp.
    """

    def __init__(self, config: DownloadConfig) -> None:
        """
        Initialize the downloader.

        :param config: Configuration object containing URLs and paths.
        :type config: DownloadConfig
        :raises ConfigurationError: If required config fields are missing.
        """
        if not config.referer or not config.embed_url:
            raise ConfigurationError("Referer and Embed URL are required.")

        self.config = config
        self.session = requests.Session()

        # Initialize headers manager
        self.headers_manager = BunnyHeaders(
            referer=config.referer, embed_url=config.embed_url
        )

        # Update session with base user agent
        self.session.headers.update(self.headers_manager.user_agent)

        self.guid: str = urlparse(config.embed_url).path.split("/")[-1]
        logger.debug(f"Initialized BunnyVideoDRM with GUID: {self.guid}")

        # Fetch and parse embed page
        self._parse_embed_page()

        # Set path
        self.path = str(Path(config.path).expanduser() if config.path else Path.cwd())

    def _parse_embed_page(self) -> None:
        """
        Fetch and parse the embed page to extract critical DRM parameters.

        Extracts:
        - Server ID
        - Context ID
        - Secret Key
        - Video Filename (if not provided in config)

        :raises NetworkError: If the embed page cannot be fetched.
        :raises ExtractionError: If regex parsing fails to find required IDs.
        """
        logger.debug(f"Fetching embed page: {self.config.embed_url}")
        try:
            embed_response = self.session.get(
                self.config.embed_url, headers=self.headers_manager.embed
            )
            embed_response.raise_for_status()
            embed_page = embed_response.text
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching embed page: {e}") from e

        # Extract Server ID
        try:
            server_id_match = re.search(
                r"https://video-(.*?)\.mediadelivery\.net", embed_page
            )
            if not server_id_match:
                raise ValueError("Could not find server ID")
            self.server_id = server_id_match.group(1)
            self.headers_manager.server_id = self.server_id
            logger.debug(f"Extracted Server ID: {self.server_id}")
        except (AttributeError, ValueError) as e:
            raise ExtractionError("Could not extract server ID.") from e

        # Extract Context ID and Secret
        try:
            search = re.search(r'contextId=(.*?)&secret=(.*?)"', embed_page)
            if not search:
                raise ValueError("Could not find context ID or secret")
            self.context_id, self.secret = search.group(1), search.group(2)
            logger.debug(f"Extracted Context ID: {self.context_id}")
        except (AttributeError, ValueError) as e:
            raise ExtractionError("Could not extract context ID and secret.") from e

        # Determine Filename
        if self.config.name:
            self.file_name = f"{self.config.name}.mp4"
        else:
            try:
                file_name_unescaped_match = re.search(
                    r'og:title" content="(.*?)"', embed_page
                )
                if file_name_unescaped_match:
                    file_name_unescaped = file_name_unescaped_match.group(1)
                    self.file_name = unescape(file_name_unescaped)
                    if not self.file_name.endswith(".mp4"):
                        self.file_name += ".mp4"
                else:
                    raise ValueError("Could not find og:title")
            except Exception as e:
                raise ExtractionError("Could not extract video title.") from e

    def _ping(self, time_pos: float, paused: str, res: str) -> None:
        """
        Send a ping request to the DRM server.

        This is required to keep the session alive and prove the user is "watching".

        :param time_pos: Current playback time position.
        :type time_pos: float
        :param paused: "true" or "false" string indicating playback state.
        :type paused: str
        :param res: Current resolution (e.g., "1080").
        :type res: str
        """
        md5_hash = md5(
            f"{self.secret}_{self.context_id}_{time_pos}_{paused}_{res}".encode("utf8")
        ).hexdigest()
        params = {
            "hash": md5_hash,
            "time": str(time_pos),
            "paused": paused,
            "chosen_res": res,
        }
        logger.debug(f"Pinging: time={time_pos}, paused={paused}, res={res}")
        try:
            self.session.get(
                f"https://video-{self.server_id}.mediadelivery.net/.drm/{self.context_id}/ping",
                params=params,
                headers=self.headers_manager.ping_activate,
            )
        except requests.RequestException:
            pass

    def _activate(self) -> None:
        """
        Activate the DRM session.

        Must be called after the initial ping and before fetching the playlist.
        """
        logger.debug("Activating session...")
        try:
            self.session.get(
                f"https://video-{self.server_id}.mediadelivery.net/.drm/{self.context_id}/activate",
                headers=self.headers_manager.ping_activate,
            )
        except requests.RequestException:
            pass

    def _get_main_playlist(self) -> str:
        """
        Fetch the main playlist and select the highest resolution.

        :return: The resolution string (e.g., "1920x1080").
        :rtype: str
        :raises NetworkError: If the playlist cannot be fetched.
        :raises PlaylistError: If no resolutions are found in the playlist.
        """
        logger.debug("Fetching main playlist...")
        params = {"contextId": self.context_id, "secret": self.secret}
        try:
            response = self.session.get(
                f"https://iframe.mediadelivery.net/{self.guid}/playlist.drm",
                params=params,
                headers=self.headers_manager.playlist,
            )
            response.raise_for_status()
            resolutions = re.findall(r"\s*(.*?)\s*/video\.drm", response.text)[::-1]
            if not resolutions:
                raise PlaylistError("No resolutions found.")

            # Programmatic selection via config
            if self.config.resolution:
                target = self.config.resolution
                for res in resolutions:
                    # Check for exact match
                    if target == res:
                        logger.info(f"Selected resolution (exact match): {res}")
                        return str(res)
                    # Check for regex/substring match
                    try:
                        if re.search(target, res):
                            logger.info(f"Selected resolution (regex match): {res}")
                            return str(res)
                    except re.error:
                        pass

                raise PlaylistError(
                    f"Requested resolution '{target}' not found in available resolutions: {resolutions}"
                )

            if self.config.interactive:
                print("\nAvailable resolutions:")
                for idx, res in enumerate(resolutions, 1):
                    print(f"{idx}. {res}")

                try:
                    choice = input(f"\nSelect resolution (1-{len(resolutions)}): ")
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(resolutions):
                        selected_res = resolutions[choice_idx]
                        logger.info(f"User selected resolution: {selected_res}")
                        return str(selected_res)
                    else:
                        raise ValueError("Invalid selection index.")
                except ValueError as e:
                    raise PlaylistError(f"Invalid resolution selection: {e}")

            logger.info(f"Selected resolution: {resolutions[0]}")
            return str(resolutions[0])
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching playlist: {e}") from e

    def _video_playlist(self, resolution: str) -> None:
        """
        Request the specific video playlist for the chosen resolution.

        This step is often required to finalize authorization for the segments.

        :param resolution: The resolution string (e.g., "1920x1080").
        :type resolution: str
        """
        logger.debug(f"Fetching video playlist for resolution: {resolution}")
        params = {"contextId": self.context_id}
        try:
            self.session.get(
                f"https://iframe.mediadelivery.net/{self.guid}/{resolution}/video.drm",
                params=params,
                headers=self.headers_manager.playlist,
            )
        except requests.RequestException:
            pass

    def _background_ping(self, resolution: str, stop_event: threading.Event) -> None:
        """
        Background thread function to send continuous pings.

        Simulates a user watching the video by incrementing the time position
        every second. This prevents the server from revoking the session token.

        :param resolution: The resolution being downloaded.
        :type resolution: str
        :param stop_event: Threading event to signal when to stop pinging.
        :type stop_event: threading.Event
        """
        logger.debug("Starting background ping thread")
        res_val = resolution.split("x")[-1]
        time_pos = 0.0
        while not stop_event.is_set():
            self._ping(
                time_pos=time_pos + round(random(), 6),
                paused="false",
                res=res_val,
            )
            time_pos += 1.0
            time.sleep(1)

    def download(self) -> None:
        """
        Start the video download process.

        1. Prepares the download (handshake).
        2. Starts the background ping thread.
        3. Invokes yt-dlp to download the HLS stream.
        4. Cleans up threads and sessions upon completion.
        """
        logger.info("Preparing download (ping, activate, playlist)...")
        self._ping(time_pos=0, paused="true", res="0")
        self._activate()
        resolution = self._get_main_playlist()
        self._video_playlist(resolution)

        # Start background pinging
        stop_event = threading.Event()
        ping_thread = threading.Thread(
            target=self._background_ping,
            args=(resolution, stop_event),
            daemon=True,
        )
        ping_thread.start()

        url = [
            f"https://iframe.mediadelivery.net/{self.guid}/{resolution}/video.drm?contextId={self.context_id}"
        ]

        logger.info(f"Video URL: {url[0]}")

        # Prepare yt-dlp options
        # Note: yt-dlp expects headers as a dictionary of strings
        ydl_headers = self.headers_manager.user_agent.copy()
        ydl_headers["Referer"] = self.config.embed_url

        ydl_opts: Dict[str, Any] = {
            "http_headers": ydl_headers,
            "concurrent_fragment_downloads": 10,
            "nocheckcertificate": True,
            "outtmpl": self.file_name,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "nopart": True,
            "paths": {
                "home": self.path,
                "temp": f".{self.file_name}/",
            },
            "retries": float("inf"),
            "extractor_retries": float("inf"),
            "fragment_retries": float("inf"),
            "skip_unavailable_fragments": False,
            "no_warnings": True,
        }

        logger.info(f"Downloading {self.file_name} to {self.path}...")
        try:
            params = cast("_Params", ydl_opts)
            with yt_dlp.YoutubeDL(params) as ydl:
                ydl.download(url)
        finally:
            stop_event.set()
            ping_thread.join()
            self.session.close()
