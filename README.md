# Bunny CDN Video Downloader

> [!WARNING]
> **ARCHIVED / DISCONTINUED**
>
> This repository is preserved for historical reasons only. The codebase has been modernized and refactored as a tribute to the original work, but **it is no longer functional**.
>
> **Recommendation:** Please use [yt-dlp](https://github.com/yt-dlp/yt-dlp) directly. It now natively supports downloading both "DRM" and non-"DRM" BunnyCDN videos without requiring external scripts.

A robust, professional-grade Python utility for downloading videos protected by Bunny CDN's "[Media Cage](https://bunny.net/stream/media-cage-video-content-protection/)" DRM system. This tool leverages `yt-dlp` for the heavy lifting while handling the complex session negotiation and header emulation required to authorize the download.

## Features

*   **Modern Architecture**: Refactored into a modular, maintainable codebase using Python 3.11+ standards.
*   **Strict Type Safety**: Fully typed codebase compliant with strict `mypy` settings.
*   **Dynamic Emulation**: Uses `ua-generator` to create realistic, randomized User-Agent strings, Client Hints, and Locale headers to mimic legitimate browser traffic.
*   **Session Persistence**: Implements background threading to send "ping" signals continuously, keeping the DRM session active throughout the entire download process.
*   **Interactive Mode**: Option to interactively select video resolution from the available playlist.
*   **CLI Interface**: A comprehensive command-line interface for flexible usage and automation.
*   **Robust Logging**: Configurable logging levels (INFO/DEBUG) and file output for transparency and troubleshooting.
*   **Developer API**: Exposes a clean, typed API for programmatic integration and parallel processing.

## Prerequisites

*   **Python 3.11+**
*   **uv**: An extremely fast Python package installer and resolver.
*   **FFmpeg**: Required by `yt-dlp` for merging video and audio streams. It is also highly recommended for faster local processing. Ensure it is installed and available in your system's PATH.

## Installation

This project uses `uv` for dependency management.

1.  Clone the repository:
    ```sh
    git clone https://github.com/yourusername/bunny-cdn-drm-video-dl.git
    cd bunny-cdn-drm-video-dl
    ```

2.  Install dependencies:
    ```sh
    uv sync
    ```

## Usage

Run the script using `uv` to ensure the virtual environment is used automatically.

### Basic Download
You must provide the **Embed URL** (where the video player is hosted) and the **Referer URL** (the website where you viewed the video).

> [!NOTE]
>
> *   The embed link typically follows this structure: [`https://iframe.mediadelivery.net/embed/{video_library_id}/{video_id}`](https://docs.bunny.net/docs/stream-embedding-videos)
> *   The referer must be a valid `http(s)://` domain (e.g., `https://example.com/`).

```sh
uv run python main.py \
    --embed-url "https://iframe.mediadelivery.net/embed/12345/12345abc-abcd-efab-cdef-abcdef123456" \
    --referer "https://example.com/"
```

### Custom Output
Specify a custom filename (without extension) and download directory.

```sh
uv run python main.py \
    -u "https://iframe.mediadelivery.net/embed/..." \
    -r "https://example.com/" \
    --name "MyCustomVideo" \
    --path "~/Downloads/Courses"
```

### Interactive Mode
List available resolutions and select one interactively.

```sh
uv run python main.py -u "..." -r "..." --interactive
```

### Advanced Options
Select a specific resolution (exact match or regex) and save logs to a file.

```sh
uv run python main.py \
    -u "..." -r "..." \
    --resolution "1080" \
    --log-file "download.log"
```

### Debug Mode
Enable verbose logging to inspect generated headers, extracted IDs, and network activity.

```sh
uv run python main.py -u "..." -r "..." --verbose
```

### Help
View all available options:

```sh
uv run python main.py --help
```

## Developer API

The project exposes a typed API for integration into other Python applications. It supports multiple instances and parallel execution.

```python
from src import BunnyVideoDRM, DownloadConfig

# Configure the download
config = DownloadConfig(
    referer="https://example.com/",
    embed_url="https://iframe.mediadelivery.net/embed/...",
    name="MyVideo",
    resolution="1080"  # Optional: Select specific resolution
)

# Initialize and run
downloader = BunnyVideoDRM(config)
downloader.download()
```

## Technical Details

This tool operates by simulating a legitimate browser session. It utilizes a [`requests.Session`](https://requests.readthedocs.io/en/latest/user/advanced/#session-objects) object to ensure cookie persistence and connection pooling across the sequence of requests:

1.  **Header Generation**: It constructs a consistent set of HTTP headers (User-Agent, Sec-CH-UA, Accept-Language) matching a specific browser/platform profile.
2.  **Handshake**: It requests the embed page to extract the Server ID, Context ID, and Secret required for authentication.
3.  **Session Activation**: It performs the cryptographic "ping" and "activate" sequence to authorize the session with Bunny CDN's servers.
4.  **Keep-Alive**: A background thread continues to send "ping" requests every second, simulating a user watching the video, which prevents the server from revoking access during long downloads.
5.  **Download**: The authorized session cookies and headers are passed to `yt-dlp`, which handles the HLS stream download and decryption (AES-128).
