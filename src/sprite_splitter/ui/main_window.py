"""Main application window – assembles canvas, side panels, menu bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QStackedWidget,
    QStatusBar,
)

from sprite_splitter import __version__
from sprite_splitter.detection.background import detect_background_color
from sprite_splitter.detection.contour import ContourDetector
from sprite_splitter.detection.grid import GridDetector
from sprite_splitter.export.manifest import write_manifest
from sprite_splitter.export.png_exporter import export_all
from sprite_splitter.models.sprite_frame import BBox, Direction, SpriteFrame, Verb, reset_frame_ids
from sprite_splitter.models.sprite_project import SpriteProject
from sprite_splitter.naming.convention import find_duplicate_filenames, find_duplicate_relative_paths
from sprite_splitter.ui.app_assets import load_logo_icon, load_logo_pixmap
from sprite_splitter.ui.animation_preview import AnimationPreview
from sprite_splitter.ui.canvas_view import CanvasView
from sprite_splitter.ui.direction_panel import DirectionPanel
from sprite_splitter.ui.export_dialog import ExportDialog
from sprite_splitter.ui.frame_panel import FramePanel
from sprite_splitter.ui.naming_dialog import NamingDialog
from sprite_splitter.ui.settings_panel import SettingsPanel
from sprite_splitter.ui.wizard_panel import WorkflowWizard


class MainWindow(QMainWindow):
    """Top-level window for Sprite Splitter."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Sprite Splitter  v{__version__}")
        self.setWindowIcon(load_logo_icon())
        self.resize(1280, 800)

        # ── model ─────────────────────────────────────────────────────────
        self._project = SpriteProject(self)

        # ── central stacked widget (canvas ↔ wizard) ─────────────────────
        self._central_stack = QStackedWidget(self)
        self._canvas = CanvasView(self)
        self._central_stack.addWidget(self._canvas)
        self.setCentralWidget(self._central_stack)

        # Wizard is created on demand after detection
        self._wizard: WorkflowWizard | None = None
        self._wizard_part1: str = ""
        self._wizard_part2: str = ""

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

        act_open = QAction("&Open Sprite Sheet(s)…", self)
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
        
        act_preview_expand = QAction("Expand Preview", self)
        act_preview_expand.setShortcut(QKeySequence("Ctrl+Shift+Up"))
        act_preview_expand.triggered.connect(lambda: self._resize_preview_dock(80))
        view_menu.addAction(act_preview_expand)
        
        act_preview_shrink = QAction("Shrink Preview", self)
        act_preview_shrink.setShortcut(QKeySequence("Ctrl+Shift+Down"))
        act_preview_shrink.triggered.connect(lambda: self._resize_preview_dock(-80))
        view_menu.addAction(act_preview_shrink)

        act_dir_panel = QAction("&Direction Panel", self)
        act_dir_panel.setShortcut(QKeySequence("Ctrl+D"))
        act_dir_panel.setCheckable(True)
        act_dir_panel.setChecked(True)
        act_dir_panel.toggled.connect(self._dir_dock.setVisible)
        self._dir_dock.visibilityChanged.connect(act_dir_panel.setChecked)
        view_menu.addAction(act_dir_panel)

        act_switch_sheet = QAction("Switch Active Sheet…", self)
        act_switch_sheet.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_switch_sheet.triggered.connect(self._switch_active_sheet)
        view_menu.addAction(act_switch_sheet)

        view_menu.addSeparator()

        act_wizard = QAction("&Workflow Wizard…", self)
        act_wizard.setShortcut(QKeySequence("Ctrl+W"))
        act_wizard.triggered.connect(lambda: self._start_wizard())
        view_menu.addAction(act_wizard)
        # Help
        help_menu = mb.addMenu("&Help")

        act_about = QAction("&About Sprite Splitter", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)
    # ==================================================================
    # Signal wiring
    # ==================================================================

    def _show_about(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("About Sprite Splitter")
        dlg.setWindowIcon(load_logo_icon())
        dlg.setModal(True)
        dlg.setMinimumWidth(560)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(load_logo_pixmap(220))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(logo)

        about_text = QLabel(
            "<h2>Sprite Splitter</h2>"
            "<p>Detect, organize, and export sprite frames.</p>"
            "<p><b>Author:</b> Justin Klutka</p>"
            "<p><b>Logo:</b> © Logo Creator / Source (used with permission)</p>"
        )
        about_text.setWordWrap(True)
        about_text.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(about_text, stretch=1)

        root.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setDefault(True)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        dlg.exec()

    def _resize_preview_dock(self, delta_px: int) -> None:
        """Resize animation preview dock vertically by a pixel delta."""
        if not self._anim_dock.isVisible():
            self._anim_dock.setVisible(True)

        current = self._anim_dock.height()
        target = max(140, current + delta_px)
        self.resizeDocks([self._anim_dock], [target], Qt.Orientation.Vertical)

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
        self._frame_panel.frame_clicked.connect(self._on_frame_clicked)
        self._frame_panel.assign_requested.connect(self._show_naming_dialog)
        self._frame_panel.delete_requested.connect(self._delete_frames)
        self._frame_panel.reorder_requested.connect(self._on_frame_reordered)

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

        proj.active_sheet_changed.connect(self._on_active_sheet_changed)

    # ==================================================================
    # Actions
    # ==================================================================

    def _open_image(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Sprite Sheet(s)", "",
            "Images (*.png *.bmp *.gif *.jpg *.jpeg);;All Files (*)",
        )
        if paths:
            try:
                self._project.load_images(paths, clear_frames=True)
                self.statusBar().showMessage(f"Loaded {len(paths)} sheet(s).")
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
            QMessageBox.warning(self, "No Image", "Load one or more sprite sheets first.")
            return

        settings = self._settings_panel.get_settings()
        self._project.settings = settings
        self.statusBar().showMessage("Detecting sprites…")
        QApplication.processEvents()

        reset_frame_ids()

        frames: list[SpriteFrame] = []
        for sheet in self._project.sheets:
            if settings.mode == "grid":
                detector = GridDetector()
                detected = detector.detect(
                    sheet.array,
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
                detected = detector.detect(
                    sheet.array,
                    settings.bg_color,
                    settings.tolerance,
                    min_area=settings.min_area,
                )

            for frame in detected:
                frame.source_sheet_id = sheet.id
                frame.source_sheet_name = sheet.path.name
            frames.extend(detected)

        self._project.set_frames(frames)
        self.statusBar().showMessage(
            f"Detected {len(frames)} sprites across {len(self._project.sheets)} sheet(s)."
        )

        # Start the workflow wizard if we got results
        if frames:
            self._start_wizard()

    def _auto_bg_color(self) -> None:
        if self._project.source_array is None:
            return
        color = detect_background_color(self._project.source_array)
        self._settings_panel.set_bg_color(color)
        self.statusBar().showMessage(
            f"Auto-detected background: RGB({color[0]}, {color[1]}, {color[2]})"
        )

    # ── workflow wizard ───────────────────────────────────────────────────

    def _start_wizard(self) -> None:
        """Create and show the three-step workflow wizard."""
        if self._wizard is not None:
            return  # already active

        self._wizard = WorkflowWizard(self)
        self._central_stack.addWidget(self._wizard)
        self._central_stack.setCurrentWidget(self._wizard)

        # Wire wizard signals
        self._wizard.review_completed.connect(self._on_wizard_review)
        self._wizard.frames_assigned.connect(self._on_wizard_assign)
        self._wizard.wizard_finished.connect(self._on_wizard_finish)
        self._wizard.wizard_cancelled.connect(self._on_wizard_cancel)

        # Hide the direction dock during the wizard (wizard has its own UI)
        self._dir_dock.hide()

        self._wizard.start(self._project.frames)
        self.statusBar().showMessage(
            "Workflow: review detected sprites, then assign metadata."
        )

    def _close_wizard(self) -> None:
        """Tear down the wizard and restore the canvas view."""
        if self._wizard is None:
            return
        self._central_stack.setCurrentWidget(self._canvas)
        self._central_stack.removeWidget(self._wizard)
        self._wizard.deleteLater()
        self._wizard = None

        # Restore direction dock
        self._dir_dock.show()

        # Refresh all views to reflect current project state
        if self._project.source_array is not None:
            self._canvas.load_image(self._project.source_array)
        self._on_frames_changed()
        self._refresh_animation_preview()
        self._refresh_direction_panel()

    def _on_wizard_review(self, rejected_ids: list[int]) -> None:
        """Remove rejected frames from the project."""
        for fid in rejected_ids:
            self._project.remove_frame(fid)

    def _on_wizard_assign(self, direction, frame_ids: list[int]) -> None:
        """Apply metadata for wizard assignment, cloning reused source frames."""
        if self._wizard is None or not isinstance(direction, Direction):
            return

        part1 = self._wizard.part1
        part2 = self._wizard.part2
        verb_text = self._wizard.current_verb

        # Resolve verb enum or custom
        verb_enum = None
        custom_verb = ""
        try:
            verb_enum = Verb(verb_text)
        except ValueError:
            custom_verb = verb_text

        # Auto-number: count existing frames in this verb+direction group
        existing = sum(
            1 for f in self._project.frames
            if f.direction == direction and f.effective_verb == verb_text
        )
        start = existing + 1

        for idx, fid in enumerate(frame_ids):
            target_id = fid
            frame = self._project.frame_by_id(fid)
            if frame is None:
                continue

            if frame.direction is not None:
                clone = self._project.clone_frame(fid)
                if clone is None:
                    continue
                target_id = clone.id

            self._project.update_frame(
                target_id,
                part1=part1,
                part2=part2,
                verb=verb_enum,
                custom_verb=custom_verb,
                direction=direction,
                frame_number=start + idx,
            )
        self._project.frames_changed.emit()

        n = len(frame_ids)
        self.statusBar().showMessage(
            f"Assigned {n} frame{'s' if n != 1 else ''} → "
            f"{part1}-{part2}-{verb_text}-{direction.value}"
        )

        # Refresh the wizard's sort page with updated model
        self._wizard.refresh_sort_page(self._project.frames)

    def _on_wizard_finish(self) -> None:
        self._close_wizard()
        self.statusBar().showMessage(
            "Workflow complete — frames are ready for export."
        )

    def _on_wizard_cancel(self) -> None:
        self._close_wizard()
        self.statusBar().showMessage("Workflow cancelled.")

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

    def _on_frame_reordered(self, ordered_ids: list[int]) -> None:
        self._project.reorder_frames(ordered_ids)
        self.statusBar().showMessage("Updated frame sequence order.")

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
        active_sheet = self._project.active_sheet
        frame = SpriteFrame(
            bbox=bbox,
            image=region,
            source_sheet_id=active_sheet.id if active_sheet is not None else 0,
            source_sheet_name=active_sheet.path.name if active_sheet is not None else "",
        )
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

        duplicate_paths = find_duplicate_relative_paths(to_export, use_folders=dlg.use_folders)
        if duplicate_paths:
            sample = list(sorted(duplicate_paths.keys()))[:5]
            details = "\n".join(f"- {path}" for path in sample)
            extra = "" if len(duplicate_paths) <= 5 else "\n- ..."
            QMessageBox.warning(
                self,
                "Export Conflict",
                "Export aborted because multiple sequence entries map to the "
                "same output file path:\n\n"
                f"{details}{extra}\n\n"
                "Adjust frame numbering or naming so every exported frame has "
                "a unique filename.",
            )
            return

        if dlg.export_manifest:
            duplicate_names = find_duplicate_filenames(to_export)
            if duplicate_names:
                sample = list(sorted(duplicate_names.keys()))[:5]
                details = "\n".join(f"- {name}" for name in sample)
                extra = "" if len(duplicate_names) <= 5 else "\n- ..."
                QMessageBox.warning(
                    self,
                    "Manifest Conflict",
                    "Export aborted because manifest frame names would collide:\n\n"
                    f"{details}{extra}\n\n"
                    "Ensure each sequence entry resolves to a unique output "
                    "filename before exporting.",
                )
                return

        try:
            paths = export_all(
                to_export,
                out_dir,
                settings.bg_color,
                settings.tolerance,
                use_folders=dlg.use_folders,
            )

            if dlg.export_manifest:
                if len(self._project.sheets) == 1 and self._project.source_path is not None:
                    src_name = self._project.source_path.name
                else:
                    src_name = "multiple-sheets"
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
        self._refresh_active_sheet_canvas()
        self._auto_bg_color()

    def _on_frames_changed(self) -> None:
        frames = self._project.frames
        self._canvas.set_frame_overlays(self._active_sheet_frames())
        self._frame_panel.set_frames(frames)

    def _on_frame_updated(self, frame_id: int) -> None:
        frame = self._project.frame_by_id(frame_id)
        if frame is None:
            return
        if frame.source_sheet_id == self._project.active_sheet_id:
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

    def _active_sheet_frames(self) -> list[SpriteFrame]:
        active_sheet_id = self._project.active_sheet_id
        if active_sheet_id is None:
            return []
        return self._project.frames_for_sheet(active_sheet_id)

    def _refresh_active_sheet_canvas(self) -> None:
        if self._project.source_array is not None:
            self._canvas.load_image(self._project.source_array)
            self._canvas.set_frame_overlays(self._active_sheet_frames())
            active = self._project.active_sheet
            if active is not None:
                self.statusBar().showMessage(f"Active sheet: {active.path.name}")
        else:
            self._canvas.clear()

    def _on_active_sheet_changed(self, _sheet_id: int) -> None:
        self._refresh_active_sheet_canvas()

    def _on_frame_clicked(self, frame_id: int) -> None:
        frame = self._project.frame_by_id(frame_id)
        if frame is None:
            return
        self._project.set_active_sheet(frame.source_sheet_id)
        self._canvas.highlight_frame(frame_id)

    def _switch_active_sheet(self) -> None:
        sheets = self._project.sheets
        if not sheets:
            QMessageBox.information(self, "Sheets", "No sheets loaded.")
            return

        names = [sheet.path.name for sheet in sheets]
        active = self._project.active_sheet
        current_name = active.path.name if active is not None else names[0]
        current_index = names.index(current_name) if current_name in names else 0
        selected, ok = QInputDialog.getItem(
            self,
            "Switch Active Sheet",
            "Sheet:",
            names,
            current_index,
            False,
        )
        if not ok:
            return
        for sheet in sheets:
            if sheet.path.name == selected:
                self._project.set_active_sheet(sheet.id)
                break
