"""Main application window – assembles canvas, side panels, menu bar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
)

from sprite_splitter.detection.background import detect_background_color
from sprite_splitter.detection.contour import ContourDetector
from sprite_splitter.detection.grid import GridDetector
from sprite_splitter.export.manifest import write_manifest
from sprite_splitter.export.png_exporter import export_all
from sprite_splitter.models.sprite_frame import BBox, SpriteFrame, reset_frame_ids
from sprite_splitter.models.sprite_project import SpriteProject
from sprite_splitter.ui.animation_preview import AnimationPreview
from sprite_splitter.ui.canvas_view import CanvasView
from sprite_splitter.ui.direction_panel import DirectionPanel
from sprite_splitter.ui.export_dialog import ExportDialog
from sprite_splitter.ui.frame_panel import FramePanel
from sprite_splitter.ui.naming_dialog import NamingDialog
from sprite_splitter.ui.settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    """Top-level window for Sprite Splitter."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sprite Splitter")
        self.resize(1280, 800)

        # ── model ─────────────────────────────────────────────────────────
        self._project = SpriteProject(self)

        # ── central canvas ────────────────────────────────────────────────
        self._canvas = CanvasView(self)
        self.setCentralWidget(self._canvas)

        # ── left dock: settings ───────────────────────────────────────────
        self._settings_panel = SettingsPanel()
        settings_dock = QDockWidget("Settings", self)
        settings_dock.setWidget(self._settings_panel)
        settings_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, settings_dock)

        # ── right dock: frame list ────────────────────────────────────────
        self._frame_panel = FramePanel()
        frame_dock = QDockWidget("Frames", self)
        frame_dock.setWidget(self._frame_panel)
        frame_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, frame_dock)

        # ── bottom dock: animation preview ────────────────────────────────
        self._anim_preview = AnimationPreview()
        self._anim_dock = QDockWidget("Animation Preview", self)
        self._anim_dock.setWidget(self._anim_preview)
        self._anim_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._anim_dock)

        # ── right dock: direction classification ──────────────────────────
        self._direction_panel = DirectionPanel()
        self._direction_panel.set_selected_ids_callback(self._frame_panel.selected_ids)
        dir_dock = QDockWidget("Direction Classification", self)
        dir_dock.setWidget(self._direction_panel)
        dir_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dir_dock)
        self._dir_dock = dir_dock

        # ── status bar ────────────────────────────────────────────────────
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready – open a sprite sheet to begin.")

        # ── menu bar ─────────────────────────────────────────────────────
        self._build_menus()

        # ── connections ──────────────────────────────────────────────────
        self._connect_signals()

    # ==================================================================
    # Menu bar
    # ==================================================================

    def _build_menus(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")

        act_open = QAction("&Open Sprite Sheet…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_image)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save_proj = QAction("&Save Project…", self)
        act_save_proj.setShortcut(QKeySequence.StandardKey.Save)
        act_save_proj.triggered.connect(self._save_project)
        file_menu.addAction(act_save_proj)

        act_load_proj = QAction("&Load Project…", self)
        act_load_proj.triggered.connect(self._load_project)
        file_menu.addAction(act_load_proj)

        file_menu.addSeparator()

        act_export = QAction("&Export Sprites…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._export)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(QApplication.quit)
        file_menu.addAction(act_quit)

        # Edit
        edit_menu = mb.addMenu("&Edit")

        act_assign = QAction("Assign &Name…", self)
        act_assign.setShortcut(QKeySequence("Ctrl+N"))
        act_assign.triggered.connect(
            lambda: self._show_naming_dialog(self._frame_panel.selected_ids())
        )
        edit_menu.addAction(act_assign)

        act_del = QAction("&Delete Selected Frames", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(
            lambda: self._delete_frames(self._frame_panel.selected_ids())
        )
        edit_menu.addAction(act_del)

        # View
        view_menu = mb.addMenu("&View")

        act_preview = QAction("&Animation Preview", self)
        act_preview.setShortcut(QKeySequence("Ctrl+P"))
        act_preview.setCheckable(True)
        act_preview.setChecked(True)
        act_preview.toggled.connect(self._anim_dock.setVisible)
        self._anim_dock.visibilityChanged.connect(act_preview.setChecked)
        view_menu.addAction(act_preview)

        act_dir_panel = QAction("&Direction Panel", self)
        act_dir_panel.setShortcut(QKeySequence("Ctrl+D"))
        act_dir_panel.setCheckable(True)
        act_dir_panel.setChecked(True)
        act_dir_panel.toggled.connect(self._dir_dock.setVisible)
        self._dir_dock.visibilityChanged.connect(act_dir_panel.setChecked)
        view_menu.addAction(act_dir_panel)

    # ==================================================================
    # Signal wiring
    # ==================================================================

    def _connect_signals(self) -> None:
        proj = self._project

        # Project → UI
        proj.project_loaded.connect(self._on_project_loaded)
        proj.frames_changed.connect(self._on_frames_changed)
        proj.frame_updated.connect(self._on_frame_updated)

        # Settings panel
        self._settings_panel.detect_requested.connect(self._run_detection)
        self._settings_panel.auto_color_button.clicked.connect(self._auto_bg_color)

        # Frame panel
        self._frame_panel.frame_clicked.connect(self._canvas.highlight_frame)
        self._frame_panel.assign_requested.connect(self._show_naming_dialog)
        self._frame_panel.delete_requested.connect(self._delete_frames)

        # Canvas
        self._canvas.frame_selected.connect(self._frame_panel.select_frame)
        self._canvas.manual_rect_drawn.connect(self._on_manual_rect)

        # Direction panel
        self._direction_panel.frames_assigned.connect(self._on_direction_assign)
        self._direction_panel.direction_selected.connect(self._on_direction_preview)

        # Animation preview – refresh whenever frames change
        proj.frames_changed.connect(self._refresh_animation_preview)
        proj.frame_updated.connect(lambda _id: self._refresh_animation_preview())

        # Keep direction panel in sync with frames
        proj.frames_changed.connect(self._refresh_direction_panel)
        proj.frame_updated.connect(lambda _id: self._refresh_direction_panel())

    # ==================================================================
    # Actions
    # ==================================================================

    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Sprite Sheet", "",
            "Images (*.png *.bmp *.gif *.jpg *.jpeg);;All Files (*)",
        )
        if path:
            try:
                self._project.load_image(path)
                self.statusBar().showMessage(f"Loaded: {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "",
            "Sprite Project (*.spriteproj);;All Files (*)",
        )
        if path:
            self._project.save_project(path)
            self.statusBar().showMessage(f"Project saved: {path}")

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "",
            "Sprite Project (*.spriteproj);;All Files (*)",
        )
        if path:
            try:
                self._project.load_project(path)
                self.statusBar().showMessage(f"Project loaded: {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── detection ─────────────────────────────────────────────────────────

    def _run_detection(self) -> None:
        if self._project.source_array is None:
            QMessageBox.warning(self, "No Image", "Load a sprite sheet first.")
            return

        settings = self._settings_panel.get_settings()
        self._project.settings = settings
        self.statusBar().showMessage("Detecting sprites…")
        QApplication.processEvents()

        reset_frame_ids()

        if settings.mode == "grid":
            detector = GridDetector()
            frames = detector.detect(
                self._project.source_array,
                settings.bg_color,
                settings.tolerance,
                cell_width=settings.cell_width,
                cell_height=settings.cell_height,
                margin=settings.margin,
                padding=settings.padding,
                auto=True,
            )
        else:
            detector = ContourDetector()
            frames = detector.detect(
                self._project.source_array,
                settings.bg_color,
                settings.tolerance,
                min_area=settings.min_area,
            )

        self._project.set_frames(frames)
        self.statusBar().showMessage(f"Detected {len(frames)} sprites.")

    def _auto_bg_color(self) -> None:
        if self._project.source_array is None:
            return
        color = detect_background_color(self._project.source_array)
        self._settings_panel.set_bg_color(color)
        self.statusBar().showMessage(
            f"Auto-detected background: RGB({color[0]}, {color[1]}, {color[2]})"
        )

    # ── naming ────────────────────────────────────────────────────────────

    def _show_naming_dialog(self, frame_ids: list[int]) -> None:
        if not frame_ids:
            QMessageBox.information(self, "Assign Name", "Select one or more frames first.")
            return

        batch = len(frame_ids) > 1
        first = self._project.frame_by_id(frame_ids[0])

        dlg = NamingDialog(
            self,
            batch=batch,
            initial_part1=first.part1 if first else "",
            initial_part2=first.part2 if first else "",
            initial_verb=first.effective_verb if first else "",
            initial_direction=first.direction.value if first and first.direction else "",
            initial_frame_number=first.frame_number if first else 1,
        )
        if dlg.exec() != NamingDialog.DialogCode.Accepted:
            return

        kwargs = {
            "part1": dlg.part1,
            "part2": dlg.part2,
            "verb": dlg.verb_enum,
            "custom_verb": dlg.custom_verb,
            "direction": dlg.direction,
        }
        if batch:
            self._project.batch_update(frame_ids, **kwargs)
        else:
            kwargs["frame_number"] = dlg.frame_number
            self._project.update_frame(frame_ids[0], **kwargs)

    def _delete_frames(self, frame_ids: list[int]) -> None:
        for fid in frame_ids:
            self._project.remove_frame(fid)

    # ── manual rect ───────────────────────────────────────────────────────

    def _on_manual_rect(self, rect: QRectF) -> None:
        """User drew a rubber-band selection on the canvas → create a frame."""
        if self._project.source_array is None:
            return
        h, w = self._project.source_array.shape[:2]
        x = max(int(rect.x()), 0)
        y = max(int(rect.y()), 0)
        bw = min(int(rect.width()), w - x)
        bh = min(int(rect.height()), h - y)
        if bw < 2 or bh < 2:
            return
        bbox = BBox(x, y, bw, bh)
        region = self._project.source_array[y:y + bh, x:x + bw].copy()
        frame = SpriteFrame(bbox=bbox, image=region)
        self._project.add_frame(frame)
        self.statusBar().showMessage(f"Added manual frame {frame.id} ({bw}×{bh}).")

    # ── direction classification ──────────────────────────────────────────

    def _on_direction_assign(self, direction, frame_ids: list[int]) -> None:
        """Assign the given direction to every frame in *frame_ids*.

        Also auto-increments frame_number for the direction group.
        """
        from sprite_splitter.models.sprite_frame import Direction as DirEnum
        if not isinstance(direction, DirEnum):
            return
        for idx, fid in enumerate(frame_ids, start=1):
            self._project.update_frame(fid, direction=direction, frame_number=idx)
        self._project.frames_changed.emit()
        n = len(frame_ids)
        self.statusBar().showMessage(
            f"Assigned {n} frame{'s' if n != 1 else ''} → {direction.value}"
        )

    def _on_direction_preview(self, direction) -> None:
        """User clicked a direction slot – jump the animation preview to it."""
        from sprite_splitter.models.sprite_frame import Direction as DirEnum
        if not isinstance(direction, DirEnum):
            return
        self._anim_preview.set_direction(direction)
        self.statusBar().showMessage(f"Previewing: {direction.value}")

    def _refresh_direction_panel(self) -> None:
        """Keep the direction panel in sync with the project frames."""
        self._direction_panel.set_frames(self._project.frames)

    # ── export ────────────────────────────────────────────────────────────

    def _export(self) -> None:
        frames = self._project.frames
        if not frames:
            QMessageBox.warning(self, "Export", "No frames to export.")
            return

        named = [f for f in frames if f.is_fully_named]
        default_dir = ""
        if self._project.source_path:
            default_dir = str(self._project.source_path.parent / "export")

        dlg = ExportDialog(self, default_dir=default_dir)
        dlg.set_frame_count(len(frames), len(named))
        if dlg.exec() != ExportDialog.DialogCode.Accepted:
            return

        to_export = named if dlg.only_named else frames
        if not to_export:
            QMessageBox.information(self, "Export", "No matching frames to export.")
            return

        out_dir = dlg.output_dir
        settings = self._project.settings

        try:
            paths = export_all(
                to_export,
                out_dir,
                settings.bg_color,
                settings.tolerance,
                use_folders=dlg.use_folders,
            )

            if dlg.export_manifest:
                src_name = (
                    self._project.source_path.name
                    if self._project.source_path else "spritesheet.png"
                )
                src_size = (0, 0)
                if self._project.source_array is not None:
                    h, w = self._project.source_array.shape[:2]
                    src_size = (w, h)
                write_manifest(
                    to_export,
                    out_dir / "manifest.json",
                    source_image_name=src_name,
                    source_size=src_size,
                )
                paths.append(out_dir / "manifest.json")

            self.statusBar().showMessage(
                f"Exported {len(paths)} files to {out_dir}"
            )
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(paths)} files to:\n{out_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ==================================================================
    # Reactive UI updates
    # ==================================================================

    def _on_project_loaded(self) -> None:
        if self._project.source_array is not None:
            self._canvas.load_image(self._project.source_array)
            self._auto_bg_color()

    def _on_frames_changed(self) -> None:
        frames = self._project.frames
        self._canvas.set_frame_overlays(frames)
        self._frame_panel.set_frames(frames)

    def _on_frame_updated(self, frame_id: int) -> None:
        frame = self._project.frame_by_id(frame_id)
        if frame is None:
            return
        self._canvas.update_frame_overlay(frame_id, frame.is_fully_named)
        self._frame_panel.update_frame(frame)

    # ==================================================================
    # Animation preview
    # ==================================================================

    def _refresh_animation_preview(self) -> None:
        """Rebuild the animation preview groups from current project state."""
        settings = self._project.settings
        self._anim_preview.set_frames(
            self._project.frames,
            bg_color=settings.bg_color,
            tolerance=settings.tolerance,
        )
