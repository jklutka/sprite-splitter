"""Logo and icon helpers for Sprite Splitter UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap


def _asset_logo_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "app_logo.png"


def load_logo_pixmap(size: int = 256) -> QPixmap:
    """Load app logo from assets, or return a generated fallback image."""
    path = _asset_logo_path()
    if path.is_file():
        pm = QPixmap(str(path))
        if not pm.isNull():
            return pm.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    # Fallback: generated monogram badge
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    rect = QRectF(4, 4, size - 8, size - 8)
    painter.setBrush(QColor(42, 46, 60))
    painter.setPen(QColor(92, 156, 230))
    painter.drawRoundedRect(rect, 24, 24)

    path_shape = QPainterPath()
    path_shape.addRoundedRect(QRectF(size * 0.18, size * 0.23, size * 0.64, size * 0.5), 14, 14)
    painter.fillPath(path_shape, QColor(25, 30, 40))

    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", max(12, size // 5), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "SS")

    painter.end()
    return pm


def load_logo_icon(size: int = 256) -> QIcon:
    """Return a QIcon for application/window icon usage."""
    return QIcon(load_logo_pixmap(size=size))
