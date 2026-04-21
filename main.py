from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pdz_assistant.app import MainWindow


def _resolve_icon_path() -> Path | None:
    if getattr(sys, "frozen", False):
        bundled_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        bundled_icon = bundled_dir / "Gemini.ico"
        if bundled_icon.exists():
            return bundled_icon

        exe_icon = Path(sys.executable).resolve().parent / "Gemini.ico"
        if exe_icon.exists():
            return exe_icon

        return None

    dev_icon = Path(__file__).resolve().parent / "Gemini.ico"
    return dev_icon if dev_icon.exists() else None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("pdz assistant python")
    app.setOrganizationName("local")

    icon_path = _resolve_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(project_root=Path(__file__).resolve().parent.parent)
    if icon_path is not None:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
