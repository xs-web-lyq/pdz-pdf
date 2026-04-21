import os
import sys
from pathlib import Path


def _register_dll_dirs() -> None:
    if not sys.platform.startswith("win"):
        return

    meipass = Path(getattr(sys, "_MEIPASS", "")).resolve()
    if not meipass.exists():
        return

    candidate_dirs = [
        meipass,
        meipass / "PySide6",
        meipass / "shiboken6",
        meipass / "_internal",
        meipass / "_internal" / "PySide6",
        meipass / "_internal" / "shiboken6",
    ]

    seen: set[str] = set()
    existing_dirs: list[str] = []
    for directory in candidate_dirs:
        directory_str = str(directory)
        if directory.exists() and directory_str not in seen:
            seen.add(directory_str)
            existing_dirs.append(directory_str)

    if not existing_dirs:
        return

    for directory_str in existing_dirs:
        try:
            os.add_dll_directory(directory_str)
        except (AttributeError, FileNotFoundError, OSError):
            pass

    current_path = os.environ.get("PATH", "")
    path_parts = [part for part in current_path.split(os.pathsep) if part]
    merged_path = os.pathsep.join(existing_dirs + path_parts)
    os.environ["PATH"] = merged_path


_register_dll_dirs()
