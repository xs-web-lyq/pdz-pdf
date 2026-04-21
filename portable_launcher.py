from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path


APP_TITLE = "pdz assistant python"


def _show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)


def main() -> int:
    bundle_root = Path(sys.executable).resolve().parent
    pythonw = bundle_root / "runtime" / "pythonw.exe"
    script = bundle_root / "app" / "main.py"

    missing = [str(path) for path in (pythonw, script) if not path.exists()]
    if missing:
        _show_error("启动失败，缺少以下文件：\n\n" + "\n".join(missing))
        return 1

    try:
        subprocess.Popen(
            [str(pythonw), str(script)],
            cwd=str(bundle_root),
            close_fds=True,
        )
    except Exception as exc:
        _show_error(f"启动失败：{exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
