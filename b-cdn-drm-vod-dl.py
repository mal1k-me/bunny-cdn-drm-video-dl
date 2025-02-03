import math
import re
import sys
from hashlib import md5
from html import unescape
from random import random
from urllib.parse import urlparse

import requests
import yt_dlp


class BunnyVideoDRM:
    # user agent and platform related headers
    user_agent = {
        "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    session.headers.update(user_agent)

    def __init__(self, referer="https://127.0.0.1/", embed_url="", name="", path=""):
        self.referer = referer if referer else sys.exit(1)
        self.embed_url = embed_url if embed_url else sys.exit(1)
        self.guid = urlparse(embed_url).path.split("/")[-1]
        self.headers = {
            "embed": {
                "authority": "iframe.mediadelivery.net",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "referer": referer,
                "sec-fetch-dest": "iframe",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "cross-site",
                "upgrade-insecure-requests": "1",
            },
            "ping|activate": {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "origin": "https://iframe.mediadelivery.net",
                "pragma": "no-cache",
                "referer": "https://iframe.mediadelivery.net/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
            },
            "playlist": {
                "authority": "iframe.mediadelivery.net",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "referer": embed_url,
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            },
        }
        embed_response = self.session.get(embed_url, headers=self.headers["embed"])
        embed_page = embed_response.text
        try:
            self.server_id = re.search(
                r"https://video-(.*?)\.mediadelivery\.net", embed_page
            ).group(1)
        except AttributeError:
            sys.exit(1)
        self.headers["ping|activate"].update(
            {"authority": f"video-{self.server_id}.mediadelivery.net"}
        )
        search = re.search(r'contextId=(.*?)&secret=(.*?)"', embed_page)
        self.context_id, self.secret = search.group(1), search.group(2)
        if name:
            self.file_name = f"{name}.mp4"
        else:
            file_name_unescaped = re.search(
                r'og:title" content="(.*?)"', embed_page
            ).group(1)
            file_name_escaped = unescape(file_name_unescaped)
            self.file_name = re.sub(r"\.[^.]*$.*", ".mp4", file_name_escaped)
            if not self.file_name.endswith(".mp4"):
                self.file_name += ".mp4"
        self.path = path if path else "~/Videos/Bunny CDN/"

    def prepare_dl(self) -> str:
        def ping(time: float, paused: str, res: str):
            md5_hash = md5(
                f"{self.secret}_{self.context_id}_{time}_{paused}_{res}".encode("utf8")
            ).hexdigest()
            params = {
                "hash": md5_hash,
                "time": time,
                "paused": paused,
                "chosen_res": res,
            }
            self.session.get(
                f"https://video-{self.server_id}.mediadelivery.net/.drm/{self.context_id}/ping",
                params=params,
                headers=self.headers["ping|activate"],
            )

        def activate():
            self.session.get(
                f"https://video-{self.server_id}.mediadelivery.net/.drm/{self.context_id}/activate",
                headers=self.headers["ping|activate"],
            )

        def main_playlist():
            params = {"contextId": self.context_id, "secret": self.secret}
            response = self.session.get(
                f"https://iframe.mediadelivery.net/{self.guid}/playlist.drm",
                params=params,
                headers=self.headers["playlist"],
            )
            resolutions = re.findall(r"\s*(.*?)\s*/video\.drm", response.text)[::-1]
            if not resolutions:
                sys.exit(2)
            return resolutions[0]  # Highest resolution

        def video_playlist():
            params = {"contextId": self.context_id}
            self.session.get(
                f"https://iframe.mediadelivery.net/{self.guid}/{resolution}/video.drm",
                params=params,
                headers=self.headers["playlist"],
            )

        # Initial ping & activation
        ping(time=0, paused="true", res="0")
        activate()

        # Fetch resolution and video URL
        resolution = main_playlist()
        video_playlist()
        video_url = f"https://iframe.mediadelivery.net/{self.guid}/{resolution}/video.drm?contextId={self.context_id}"

        # Get video duration using yt-dlp
        ydl_opts = {
            "quiet": True,
            "simulate": True,
            "nocheckcertificate": True,
            "http_headers": {
                "Referer": self.embed_url,
                "User-Agent": self.user_agent["user-agent"],
            },
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                duration = info.get("duration", 0)  # Fallback to 0 if unavailable
        except Exception as e:
            print(f"Error fetching duration: {e}, using default 30 seconds")
            duration = 30  # Default duration if extraction fails

        # Calculate ping intervals (every 4 seconds up to video duration)
        step = 4
        max_time = math.ceil(duration) if duration > 0 else 30  # Ensure minimum coverage

        # Send adaptive pings
        t = 0
        while t <= max_time:
            ping_time = t + round(random(), 6)
            ping(time=ping_time, paused="false", res=resolution.split("x")[-1])
            t += step

        self.session.close()
        return resolution


    def download(self):
        resolution = self.prepare_dl()
        url = [
            f"https://iframe.mediadelivery.net/{self.guid}/{resolution}/video.drm?contextId={self.context_id}"
        ]
        ydl_opts = {
            "http_headers": {
                "Referer": self.embed_url,
                "User-Agent": self.user_agent["user-agent"],
            },
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(url)


if __name__ == '__main__':
    video = BunnyVideoDRM(
        # insert the referer between the quotes below (address of your webpage)
        referer='',
        # paste your embed link
        embed_url='',
        # you can override file name, no extension
        name="",
        # you can override download path
        path=r""
    )
    # video.session.close()
    video.download()
