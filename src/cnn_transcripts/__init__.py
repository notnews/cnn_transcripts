"""Scraper and provenance record for the CNN Transcripts 2000--2025 corpus."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cnn-transcripts")
except PackageNotFoundError:  # pragma: no cover - not installed
    __version__ = "0.0.0"
