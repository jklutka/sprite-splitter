"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from sprite_splitter.ui.main_window import MainWindow
from sprite_splitter.ui.app_assets import load_logo_icon


def main() -> None:
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Sprite Splitter")
    app.setOrganizationName("SpriteSplitter")
    app.setWindowIcon(load_logo_icon())

    # Apply a dark palette for a game-dev-friendly look
    _apply_dark_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def _apply_dark_theme(app: QApplication) -> None:
    """Apply a minimal dark stylesheet."""
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background: #2b2b2b;
            color: #ddd;
        }
        QMenuBar {
            background: #333;
            color: #ddd;
        }
        QMenuBar::item:selected {
            background: #555;
        }
        QMenu {
            background: #333;
            color: #ddd;
        }
        QMenu::item:selected {
            background: #555;
        }
        QDockWidget {
            color: #ddd;
        }
        QDockWidget::title {
            background: #383838;
            padding: 4px;
        }
        QLabel {
            color: #ccc;
        }
        QLineEdit, QSpinBox, QComboBox {
            background: #3c3c3c;
            color: #ddd;
            border: 1px solid #555;
            padding: 3px;
            border-radius: 3px;
        }
        QListWidget {
            background: #2f2f2f;
            color: #ddd;
            border: 1px solid #444;
        }
        QListWidget::item:selected {
            background: #3a6ea5;
        }
        QPushButton {
            background: #444;
            color: #ddd;
            padding: 5px 12px;
            border: 1px solid #555;
            border-radius: 3px;
        }
        QPushButton:hover {
            background: #555;
        }
        QPushButton:pressed {
            background: #333;
        }
        QSlider::groove:horizontal {
            background: #555;
            height: 6px;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #888;
            width: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 12px;
            color: #ccc;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
        QCheckBox {
            color: #ccc;
        }
        QStatusBar {
            background: #333;
            color: #aaa;
        }
        QScrollBar:vertical, QScrollBar:horizontal {
            background: #2b2b2b;
        }
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background: #555;
            border-radius: 3px;
        }
        QStackedWidget {
            background: #2b2b2b;
        }
        QScrollArea {
            background: #2b2b2b;
        }
    """)


if __name__ == "__main__":
    main()
