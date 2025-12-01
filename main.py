import argparse
import logging
import sys

from src.config import DownloadConfig
from src.downloader import BunnyVideoDRM
from src.exceptions import BunnyVideoError


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    :return: Parsed arguments namespace containing embed_url, referer, name, path, verbose, interactive, resolution, and log_file flags.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Bunny CDN DRM Video Downloader",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-u",
        "--embed-url",
        type=str,
        required=True,
        help="The embed URL of the video (e.g., https://iframe.mediadelivery.net/embed/...)",
    )
    parser.add_argument(
        "-r",
        "--referer",
        type=str,
        required=True,
        help="The referer URL (website domain) where the video is embedded",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Override the output video filename (without extension)",
    )
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        help="Override the download directory path",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enable interactive resolution selection",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        help="Programmatically select resolution (exact match or regex)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to a file where logs should be written",
    )
    return parser.parse_args()


def setup_logging(verbose: bool, log_file: str | None = None) -> None:
    """
    Configure the logging system.

    Sets up a stream handler to stdout and optionally a file handler.

    :param verbose: If True, set logging level to DEBUG, otherwise INFO.
    :type verbose: bool
    :param log_file: Optional path to a log file.
    :type log_file: str | None
    """
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def main() -> None:
    """
    Main entry point for the application.

    Orchestrates the download process:
    1. Parses command-line arguments.
    2. Sets up logging configuration.
    3. Initializes the download configuration.
    4. Instantiates the downloader and starts the process.
    5. Handles known and unexpected exceptions gracefully.
    """
    args = parse_args()
    setup_logging(args.verbose, args.log_file)

    logger = logging.getLogger("main")
    logger.info("Initializing downloader...")

    try:
        # Initialize configuration from command-line arguments
        config = DownloadConfig(
            referer=args.referer,
            embed_url=args.embed_url,
            name=args.name,
            path=args.path,
            interactive=args.interactive,
            resolution=args.resolution,
            log_file=args.log_file,
        )

        logger.debug(f"Configuration loaded: {config}")

        # Instantiate the downloader with the config
        video = BunnyVideoDRM(config)

        logger.info(f"Prepared download for: {video.file_name}")

        # Start the download process
        video.download()

        logger.info("Download process finished.")

    except BunnyVideoError as e:
        # Handle expected errors (configuration, network, extraction)
        logger.error(f"Download failed: {e}")
        if args.verbose:
            logger.exception("Traceback:")
        sys.exit(1)
    except Exception as e:
        # Handle unexpected crashes
        logger.critical(f"An unexpected error occurred: {e}")
        if args.verbose:
            logger.exception("Traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
