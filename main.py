from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from pdz_assistant.app import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("pdz assistant python")
    app.setOrganizationName("local")

    window = MainWindow(project_root=Path(__file__).resolve().parent.parent)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
