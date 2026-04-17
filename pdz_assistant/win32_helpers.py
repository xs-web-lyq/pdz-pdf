from __future__ import annotations

import re

import win32api
import win32con
import win32gui
import win32process


def get_hwnd_for_pid(pid: int) -> int | None:
    matches: list[int] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if window_pid == pid and win32gui.GetWindowText(hwnd):
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(callback, 0)
    return matches[0] if matches else None


def get_foreground_window() -> int | None:
    hwnd = win32gui.GetForegroundWindow()
    return hwnd or None


def is_window_maximized(hwnd: int) -> bool:
    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    return show_cmd == win32con.SW_SHOWMAXIMIZED


def is_window_minimized(hwnd: int) -> bool:
    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    return show_cmd == win32con.SW_SHOWMINIMIZED


def show_window_maximized(hwnd: int) -> None:
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)


def make_lparam(low: int, high: int) -> int:
    return ((high & 0xFFFF) << 16) | (low & 0xFFFF)


def send_key(hwnd: int, virtual_key: int, delay_ms: int = 1) -> None:
    scan_code = win32api.MapVirtualKey(virtual_key, 0)
    down_lparam = 1 | (scan_code << 16)
    up_lparam = down_lparam | 0xC0000000
    win32gui.SendMessage(hwnd, win32con.WM_KEYDOWN, virtual_key, down_lparam)
    win32gui.SendMessage(hwnd, win32con.WM_KEYUP, virtual_key, up_lparam)
    if delay_ms > 0:
        win32api.Sleep(delay_ms)


def click_client_point(hwnd: int, x: int, y: int) -> None:
    lparam = make_lparam(x, y)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def get_primary_screen_size() -> tuple[int, int]:
    return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)


def natural_sort_key(path_name: str) -> list[object]:
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r'(\d+)', path_name)]
