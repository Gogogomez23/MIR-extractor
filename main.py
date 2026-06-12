import os
import sys
from PyQt6.QtWidgets import QApplication
from core.database import init_db
from ui.main_window import MainWindow


def main():
    # 1. Boot internal storage frameworks schemas local databases file systems
    init_db()

    # 2. Render graphics application contexts loop
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"

if __name__ == "__main__":
    main()