from __future__ import annotations

import sys
from pathlib import Path

from cx_Freeze import Executable, setup


ROOT = Path(__file__).resolve().parent

build_exe_options = {
    "packages": [
        "pdz_assistant",
        "fitz",
        "PIL",
        "psutil",
        "pymem",
        "win32api",
        "win32con",
        "win32gui",
        "win32process",
    ],
    "include_files": [
        (str(ROOT / "Gemini.ico"), "Gemini.ico"),
    ],
    "include_msvcr": True,
    # Keep packages unpacked on disk to stay close to the working wheel layout.
    "zip_include_packages": [],
    "zip_exclude_packages": ["*"],
}

base = "Win32GUI" if sys.platform == "win32" else None

executables = [
    Executable(
        script=str(ROOT / "main.py"),
        base=base,
        target_name="pdz-assistant-python.exe",
        icon=str(ROOT / "Gemini.ico"),
    )
]

setup(
    name="pdz-assistant-python",
    version="1.0.0",
    description="Standalone build of the pdz assistant Python edition",
    options={"build_exe": build_exe_options},
    executables=executables,
)
