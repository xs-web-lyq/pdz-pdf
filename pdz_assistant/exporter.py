from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Callable

import fitz
from PIL import Image

from .models import ExportConfig, ExportResult, ProgressUpdate
from .reader import SsReaderController
from .win32_helpers import natural_sort_key, show_window_maximized


class ExportCancelled(Exception):
    pass


class ExportService:
    def __init__(self, reader: SsReaderController) -> None:
        self._reader = reader
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run_export(
        self,
        hwnd: int,
        config: ExportConfig,
        progress: Callable[[ProgressUpdate], None],
        ask_continue: Callable[[int, int], bool],
    ) -> ExportResult:
        self._cancel_event.clear()
        config.png_dir.mkdir(parents=True, exist_ok=True)
        config.pdf_path.parent.mkdir(parents=True, exist_ok=True)
        config.temp_buffer_dir.mkdir(parents=True, exist_ok=True)

        progress(ProgressUpdate("\u6b63\u5728\u9501\u5b9a ssReader \u7a97\u53e3\u5e76\u51c6\u5907\u8f6c\u6362", 5))
        self._clear_directory_contents(config.png_dir)
        self._clear_directory_contents(config.temp_buffer_dir)

        show_window_maximized(hwnd)
        self._reader.press_home(hwnd)

        stagnant_count = 0
        previous_bmp_count = 0
        forced_merge = False

        while True:
            self._ensure_not_cancelled()
            show_window_maximized(hwnd)
            self._reader.press_page_down(hwnd)
            time.sleep(0.01)

            bmp_count = self._count_bmp_files(config.temp_buffer_dir)
            if bmp_count >= config.total_pages or forced_merge:
                progress(ProgressUpdate("bmp \u91ca\u653e\u5b8c\u6210\uff0c\u6b63\u5728\u8f6c\u6362\u4e3a png", 20))
                png_count = self._convert_bmps_to_pngs(config.temp_buffer_dir, config.png_dir, progress)
                progress(ProgressUpdate("png \u8f6c\u6362\u5b8c\u6210\uff0c\u6b63\u5728\u5408\u6210 pdf", 60))
                output_pdf = self._compose_pdf(config.png_dir, config.pdf_path)
                if config.delete_png_after_pdf:
                    self._clear_directory_contents(config.png_dir)
                return ExportResult(True, png_count, output_pdf, "pdf \u751f\u6210\u6210\u529f")

            stagnant_count = stagnant_count + 1 if previous_bmp_count == bmp_count else 0
            if stagnant_count >= 1000:
                missing_pages = max(config.total_pages - bmp_count, 0)
                should_continue = ask_continue(config.total_pages, missing_pages)
                if should_continue:
                    forced_merge = True
                    stagnant_count = 0
                else:
                    return ExportResult(False, bmp_count, None, "\u7528\u6237\u53d6\u6d88\u4e86\u5bfc\u51fa")

            previous_bmp_count = bmp_count

    def _convert_bmps_to_pngs(
        self,
        buffer_dir: Path,
        png_dir: Path,
        progress: Callable[[ProgressUpdate], None],
    ) -> int:
        bmp_files = sorted(buffer_dir.rglob("*.bmp"), key=lambda item: natural_sort_key(item.name))
        total = len(bmp_files)
        for index, bmp_path in enumerate(bmp_files, start=1):
            self._ensure_not_cancelled()
            png_path = png_dir / f"{index}.png"
            with Image.open(bmp_path) as image:
                image.save(png_path, format="PNG")
            percent = 20 + int((index / max(total, 1)) * 35)
            progress(ProgressUpdate(f"\u6b63\u5728\u8f6c\u6362\u56fe\u7247 {index}/{total}", percent))
        return total

    def _compose_pdf(self, png_dir: Path, pdf_path: Path) -> Path:
        png_files = sorted(png_dir.rglob("*.png"), key=lambda item: natural_sort_key(item.name))
        document = fitz.open()
        try:
            for png_path in png_files:
                self._ensure_not_cancelled()
                with Image.open(png_path) as image:
                    width, height = image.size
                page = document.new_page(width=width, height=height)
                page.insert_image(page.rect, filename=str(png_path))
            document.save(pdf_path)
        finally:
            document.close()
        return pdf_path

    def _clear_directory_contents(self, directory: Path) -> None:
        if not directory.exists():
            return
        for child in directory.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)

    def _count_bmp_files(self, buffer_dir: Path) -> int:
        if not buffer_dir.exists():
            return 0
        return sum(1 for _ in buffer_dir.rglob("*.bmp"))

    def _ensure_not_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise ExportCancelled()
