"""Welcome / start screen shown when no project is active."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.ui.app_assets import load_logo_pixmap


class StartScreen(QWidget):
    """Shown at app launch — lets the user begin a new character or open a project."""

    new_character_requested = Signal()
    open_project_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner = QVBoxLayout()
        inner.setSpacing(0)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo
        logo_lbl = QLabel()
        px = load_logo_pixmap()
        if not px.isNull():
            logo_lbl.setPixmap(
                px.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(logo_lbl)
            inner.addSpacing(12)

        # Title
        title = QLabel("Sprite Splitter")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #eee;")
        inner.addWidget(title)
        inner.addSpacing(8)

        subtitle = QLabel("Split, sequence, and export sprite animations")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #777;")
        inner.addWidget(subtitle)
        inner.addSpacing(40)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_new = QPushButton("New Character")
        self._btn_new.setFixedSize(180, 52)
        self._btn_new.setStyleSheet(
            "QPushButton { background: #3a6ea5; color: #fff; font-size: 14px; "
            "font-weight: bold; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #4a8ec5; }"
            "QPushButton:pressed { background: #2a5e95; }"
        )
        self._btn_new.clicked.connect(self.new_character_requested)
        btn_row.addWidget(self._btn_new)

        self._btn_open = QPushButton("Open Project\u2026")
        self._btn_open.setFixedSize(180, 52)
        self._btn_open.setStyleSheet(
            "QPushButton { background: #353535; color: #ccc; font-size: 14px; "
            "border: 1px solid #555; border-radius: 6px; }"
            "QPushButton:hover { background: #454545; color: #fff; }"
            "QPushButton:pressed { background: #252525; }"
        )
        self._btn_open.clicked.connect(self.open_project_requested)
        btn_row.addWidget(self._btn_open)

        inner.addLayout(btn_row)
        inner.addSpacing(20)

        hint = QLabel("Start by naming your character, then load sprite sheets.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 11px; color: #555;")
        inner.addWidget(hint)

        outer.addLayout(inner)
