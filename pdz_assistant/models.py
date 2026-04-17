from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ReaderState:
    pid: int | None
    hwnd: int | None
    is_running: bool
    is_foreground: bool
    is_maximized: bool
    is_minimized: bool
    is_reading_mode: bool
    total_pages: int | None
    status_text: str
    diagnostic_message: str = ""
    diagnostic_log_path: Path | None = None


@dataclass(slots=True)
class ExportConfig:
    png_dir: Path
    pdf_path: Path
    temp_buffer_dir: Path
    total_pages: int
    delete_png_after_pdf: bool


@dataclass(slots=True)
class ProgressUpdate:
    message: str
    percent: int
    is_error: bool = False


@dataclass(slots=True)
class ExportResult:
    success: bool
    generated_pages: int
    output_pdf: Path | None
    message: str
