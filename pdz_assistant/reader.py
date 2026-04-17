from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import traceback

import psutil
import pymem
import pymem.exception
import pymem.process
import win32con

from .models import ReaderState
from .win32_helpers import (
    click_client_point,
    get_foreground_window,
    get_hwnd_for_pid,
    get_primary_screen_size,
    is_window_maximized,
    is_window_minimized,
    send_key,
)


@dataclass(frozen=True, slots=True)
class PointerSpec:
    base_offset: int
    chain: tuple[int, ...]


class SsReaderController:
    PROCESS_NAME = "ssReader.exe"
    BASE_POINTER = 0x00598C54
    TAB_SPEC = PointerSpec(BASE_POINTER, (0x0, 0x130, 0x3C, 0x8C, 0x84, 0x44, 0x598))
    PREFACE_SPEC = PointerSpec(BASE_POINTER, (0x0, 0x164, 0x654, 0x390))
    CONTENTS_SPEC = PointerSpec(BASE_POINTER, (0x0, 0x164, 0x654, 0x394))
    BODY_SPEC = PointerSpec(BASE_POINTER, (0x0, 0x164, 0x654, 0x398))

    def __init__(self) -> None:
        self.log_dir = Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_state(self) -> ReaderState:
        process = self._find_process()
        if process is None:
            return ReaderState(
                pid=None,
                hwnd=None,
                is_running=False,
                is_foreground=False,
                is_maximized=False,
                is_minimized=False,
                is_reading_mode=False,
                total_pages=None,
                status_text="\u5173",
                diagnostic_message="ssReader \u672a\u542f\u52a8",
                diagnostic_log_path=None,
            )

        hwnd = get_hwnd_for_pid(process.pid)
        foreground = get_foreground_window()
        total_pages, reading_mode, diagnostic_message, log_path = self._read_total_pages(process.pid)

        return ReaderState(
            pid=process.pid,
            hwnd=hwnd,
            is_running=True,
            is_foreground=bool(hwnd and hwnd == foreground),
            is_maximized=bool(hwnd and is_window_maximized(hwnd)),
            is_minimized=bool(hwnd and is_window_minimized(hwnd)),
            is_reading_mode=reading_mode,
            total_pages=total_pages,
            status_text="\u5f00",
            diagnostic_message=diagnostic_message,
            diagnostic_log_path=log_path,
        )

    def press_home(self, hwnd: int) -> None:
        send_key(hwnd, win32con.VK_HOME)

    def press_page_down(self, hwnd: int) -> None:
        send_key(hwnd, win32con.VK_NEXT)

    def switch_to_dual_page_mode(self, hwnd: int) -> None:
        width, height = get_primary_screen_size()
        click_client_point(hwnd, int(width * (170 / 1920)), int(height * (75 / 1080)))

    def switch_to_continuous_mode(self, hwnd: int) -> None:
        width, height = get_primary_screen_size()
        click_client_point(hwnd, int(width * (140 / 1920)), int(height * (75 / 1080)))

    def _find_process(self) -> psutil.Process | None:
        for process in psutil.process_iter(["pid", "name"]):
            name = process.info.get("name") or ""
            if name.lower() == self.PROCESS_NAME.lower() or name.lower() == "ssreader":
                return process
        return None

    def _read_total_pages(self, pid: int) -> tuple[int | None, bool, str, Path | None]:
        trace_lines: list[str] = []
        try:
            pm = pymem.Pymem()
            pm.open_process_from_id(pid)
            module = pymem.process.module_from_name(pm.process_handle, self.PROCESS_NAME)
            base_address = module.lpBaseOfDll
            is_target_64 = pymem.process.is_64_bit(pm.process_handle)
            trace_lines.append(f"base_address={hex(base_address)}")
            trace_lines.append(f"is_target_64={is_target_64}")

            tab_value = self._read_pointer_chain_int(pm, base_address, self.TAB_SPEC, is_target_64, trace_lines, "tab")
            if tab_value == 0:
                return None, False, "ssReader \u672a\u5904\u4e8e\u9605\u8bfb\u6a21\u5f0f", None

            preface = self._read_pointer_chain_int(pm, base_address, self.PREFACE_SPEC, is_target_64, trace_lines, "preface")
            contents = self._read_pointer_chain_int(pm, base_address, self.CONTENTS_SPEC, is_target_64, trace_lines, "contents")
            body = self._read_pointer_chain_int(pm, base_address, self.BODY_SPEC, is_target_64, trace_lines, "body")
            trace_lines.append(f"preface={preface}")
            trace_lines.append(f"contents={contents}")
            trace_lines.append(f"body={body}")
            return preface + contents + body, True, "", None
        except pymem.exception.CouldNotOpenProcess as exc:
            log_path = self._write_diagnostic_log(pid, exc, trace_lines)
            return (
                None,
                False,
                f"\u65e0\u6cd5\u8bfb\u53d6 ssReader \u5185\u5b58\uff0c\u8bf7\u5c1d\u8bd5\u4f7f\u7528\u7ba1\u7406\u5458\u6743\u9650\u542f\u52a8\u672c\u5de5\u5177\uff0c\u5e76\u786e\u4fdd ssReader \u4e0e\u672c\u5de5\u5177\u7684\u6743\u9650\u7ea7\u522b\u4e00\u81f4\uff08\u65e5\u5fd7\uff1a{log_path.name}\uff09",
                log_path,
            )
        except Exception as exc:
            log_path = self._write_diagnostic_log(pid, exc, trace_lines)
            return None, False, f"\u8bfb\u53d6 ssReader \u9875\u6570\u5931\u8d25\uff08\u65e5\u5fd7\uff1a{log_path.name}\uff09", log_path

    def _read_pointer_chain_int(
        self,
        pm: pymem.Pymem,
        module_base: int,
        spec: PointerSpec,
        is_target_64: bool,
        trace_lines: list[str],
        label: str,
    ) -> int:
        base_ptr_address = module_base + spec.base_offset
        address = self._read_pointer(pm, base_ptr_address, is_target_64)
        trace_lines.append(f"{label}: read_ptr({hex(base_ptr_address)}) -> {hex(address)}")
        for index, offset in enumerate(spec.chain[:-1], start=1):
            next_address = address + offset
            address = self._read_pointer(pm, next_address, is_target_64)
            trace_lines.append(f"{label}: level{index} read_ptr({hex(next_address)}) -> {hex(address)}")
        final_address = address + spec.chain[-1]
        value = pm.read_int(final_address)
        trace_lines.append(f"{label}: read_int({hex(final_address)}) -> {value}")
        return value

    def _read_pointer(self, pm: pymem.Pymem, address: int, is_target_64: bool) -> int:
        if is_target_64:
            return pm.read_ulonglong(address)
        return pm.read_uint(address)

    def _write_diagnostic_log(self, pid: int, exc: Exception, trace_lines: list[str]) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.log_dir / f"reader_diagnostic_{pid}_{timestamp}.log"
        content = [
            f"time: {datetime.now().isoformat()}",
            f"pid: {pid}",
            f"process_name: {self.PROCESS_NAME}",
            f"exception_type: {type(exc).__name__}",
            f"exception: {exc!r}",
            "trace:",
            *trace_lines,
            "traceback:",
            traceback.format_exc(),
        ]
        log_path.write_text("\n".join(content), encoding="utf-8")
        return log_path
