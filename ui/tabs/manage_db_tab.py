import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from core.database import (
    clear_all_data,
    clear_questions_only,
    delete_batch,
    get_all_questions,
    get_database_stats,
    get_extractions,
    init_db,
)


def _build_batch_export_template(batch, questions):
    lines = []
    lines.append("MIR Batch Export")
    lines.append("=" * 80)
    lines.append(f"Batch ID: {batch['id']}")
    lines.append(f"Filename: {batch.get('filename') or ''}")
    lines.append(f"Page Range: {batch.get('page_range') or ''}")
    lines.append(f"Timestamp: {batch.get('timestamp') or ''}")
    lines.append(f"Question Count: {len(questions)}")
    lines.append("=" * 80)
    lines.append("")

    for idx, question in enumerate(questions, start=1):
        lines.append(f"Question {idx}")
        lines.append(f"Reference: MIR {question['ano']} - Q{question['num']}")
        lines.append(f"Status: {question.get('status') or ''}")
        lines.append(f"Revised: {'Yes' if int(question.get('revised', 0)) else 'No'}")
        lines.append("")
        lines.append("Enunciado:")
        lines.append(question.get("enunciado") or "")
        lines.append("")
        lines.append("Opciones:")
        for opt_idx, option in enumerate(question.get("opciones", []), start=1):
            lines.append(f"  {opt_idx}. {option}")
        lines.append("")
        lines.append(f"RC: {question.get('rc') or ''}")
        lines.append(f"Tema: {question.get('tema') or ''}")
        lines.append(f"Especialidad: {question.get('especialidad') or ''}")
        lines.append(f"Dificultad: {question.get('dificultad') or ''}")
        lines.append("Explicacion:")
        lines.append(question.get("explicacion") or "")
        lines.append("-" * 80)
        lines.append("")

    return "\n".join(lines)


class DatabaseAdminWorker(QThread):
    result_ready = pyqtSignal(str, object)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, action, payload=None):
        super().__init__()
        self.action = action
        self.payload = payload or {}

    def run(self):
        try:
            if self.action == "delete_batch":
                result = delete_batch(self.payload["extraction_id"])
            elif self.action == "purge_questions":
                result = clear_questions_only()
            elif self.action == "nuke_database":
                result = clear_all_data()
                init_db()
                result["database_reinitialized"] = True
            elif self.action == "export_batch":
                result = self._export_selected_batch()
            else:
                raise ValueError(f"Unsupported database action: {self.action}")

            self.result_ready.emit(self.action, result)
        except Exception as exc:
            self.error_occurred.emit(self.action, str(exc))

    def _export_selected_batch(self):
        extraction_id = self.payload["extraction_id"]
        save_path = self.payload["save_path"]

        batches = get_extractions()
        batch = next((row for row in batches if row["id"] == extraction_id), None)
        if batch is None:
            raise ValueError("Selected batch no longer exists.")

        questions = get_all_questions(extraction_id=extraction_id)
        if not questions:
            raise ValueError("Selected batch does not contain any questions.")

        content = _build_batch_export_template(batch, questions)
        with open(save_path, "w", encoding="utf-8") as handle:
            handle.write(content)

        return {
            "save_path": save_path,
            "batch_id": extraction_id,
            "question_count": len(questions),
        }


class ManageDBTab(QWidget):
    database_mutated = pyqtSignal()
    batch_open_requested = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_batch_id = None
        self.current_worker = None
        self.init_ui()
        self.refresh_dashboard()

    def init_ui(self):
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title = QLabel("Database Administrator Panel")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        header_row.addWidget(title)
        header_row.addStretch()

        self.btn_refresh = QPushButton("Refresh View")
        self.btn_refresh.clicked.connect(self.refresh_dashboard)
        header_row.addWidget(self.btn_refresh)
        layout.addLayout(header_row)

        log_group = QGroupBox("Extractions Log")
        log_layout = QVBoxLayout(log_group)

        self.lbl_log_hint = QLabel("Double-click a batch to open it in the Edit tab.")
        self.lbl_log_hint.setStyleSheet("color: #6b7280;")
        log_layout.addWidget(self.lbl_log_hint)

        self.table_extractions = QTableWidget(0, 4)
        self.table_extractions.setHorizontalHeaderLabels(
            ["ID", "Filename", "Page Range", "Timestamp"]
        )
        self.table_extractions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_extractions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_extractions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_extractions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_extractions.itemSelectionChanged.connect(self.handle_selection_changed)
        self.table_extractions.cellDoubleClicked.connect(self.open_selected_batch_in_editor)
        log_layout.addWidget(self.table_extractions)
        layout.addWidget(log_group)

        batch_group = QGroupBox("Batch Operations")
        batch_layout = QHBoxLayout(batch_group)

        self.btn_delete_batch = QPushButton("Delete Selected Batch")
        self.btn_delete_batch.setStyleSheet("background-color: #b91c1c; color: white; font-weight: bold;")
        self.btn_delete_batch.clicked.connect(self.delete_selected_batch)
        batch_layout.addWidget(self.btn_delete_batch)

        self.btn_export_batch = QPushButton("Export Selected Batch")
        self.btn_export_batch.clicked.connect(self.export_selected_batch)
        batch_layout.addWidget(self.btn_export_batch)

        layout.addWidget(batch_group)

        maintenance_group = QGroupBox("Global Maintenance")
        maintenance_layout = QHBoxLayout(maintenance_group)

        self.btn_purge_questions = QPushButton("Purge All Questions")
        self.btn_purge_questions.setStyleSheet("background-color: #f59e0b; color: black; font-weight: bold;")
        self.btn_purge_questions.clicked.connect(self.purge_all_questions)
        maintenance_layout.addWidget(self.btn_purge_questions)

        self.btn_nuke_database = QPushButton("Nuke Entire Database")
        self.btn_nuke_database.setStyleSheet("background-color: #7f1d1d; color: white; font-weight: bold;")
        self.btn_nuke_database.clicked.connect(self.nuke_entire_database)
        maintenance_layout.addWidget(self.btn_nuke_database)

        layout.addWidget(maintenance_group)

        metrics_group = QGroupBox("Global Metrics")
        metrics_layout = QGridLayout(metrics_group)

        self.lbl_total_batches = QLabel("0")
        self.lbl_total_questions = QLabel("0")
        self.lbl_total_revised = QLabel("0")
        self.lbl_total_pending = QLabel("0")

        metrics_layout.addWidget(QLabel("Total Batches:"), 0, 0)
        metrics_layout.addWidget(self.lbl_total_batches, 0, 1)
        metrics_layout.addWidget(QLabel("Total Extracted Questions:"), 1, 0)
        metrics_layout.addWidget(self.lbl_total_questions, 1, 1)
        metrics_layout.addWidget(QLabel("Total Revised Items:"), 2, 0)
        metrics_layout.addWidget(self.lbl_total_revised, 2, 1)
        metrics_layout.addWidget(QLabel("Total Remaining Items Pending Review:"), 3, 0)
        metrics_layout.addWidget(self.lbl_total_pending, 3, 1)

        layout.addWidget(metrics_group)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color: #4b5563;")
        layout.addWidget(self.lbl_status)

        self.update_action_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        self.load_extractions()
        self.update_metrics()

    def load_extractions(self, select_batch_id=None):
        selected_id = self.selected_batch_id if select_batch_id is None else select_batch_id
        batches = get_extractions()

        self.table_extractions.blockSignals(True)
        try:
            self.table_extractions.clearContents()
            self.table_extractions.setRowCount(0)

            for row_idx, batch in enumerate(batches):
                self.table_extractions.insertRow(row_idx)

                id_item = QTableWidgetItem(str(batch["id"]))
                id_item.setData(Qt.ItemDataRole.UserRole, batch["id"])
                filename_item = QTableWidgetItem(batch.get("filename") or "")
                page_range_item = QTableWidgetItem(batch.get("page_range") or "")
                timestamp_item = QTableWidgetItem(batch.get("timestamp") or "")

                self.table_extractions.setItem(row_idx, 0, id_item)
                self.table_extractions.setItem(row_idx, 1, filename_item)
                self.table_extractions.setItem(row_idx, 2, page_range_item)
                self.table_extractions.setItem(row_idx, 3, timestamp_item)

            self._restore_selection(selected_id, batches)
        finally:
            self.table_extractions.blockSignals(False)

        self.handle_selection_changed()

    def _restore_selection(self, selected_id, batches):
        if selected_id is None:
            self.table_extractions.clearSelection()
            self.selected_batch_id = None
            return

        for row_idx, batch in enumerate(batches):
            if batch["id"] == selected_id:
                self.table_extractions.selectRow(row_idx)
                self.table_extractions.setCurrentCell(row_idx, 0)
                self.selected_batch_id = selected_id
                return

        self.table_extractions.clearSelection()
        self.selected_batch_id = None

    def handle_selection_changed(self):
        self.selected_batch_id = self._get_selected_batch_id()
        self.update_action_buttons()

    def _get_selected_batch_id(self):
        current_row = self.table_extractions.currentRow()
        if current_row < 0:
            return None

        id_item = self.table_extractions.item(current_row, 0)
        if id_item is None:
            return None

        return id_item.data(Qt.ItemDataRole.UserRole)

    def _get_selected_batch_record(self):
        current_row = self.table_extractions.currentRow()
        if current_row < 0:
            return None

        id_item = self.table_extractions.item(current_row, 0)
        if id_item is None:
            return None

        batch_id = id_item.data(Qt.ItemDataRole.UserRole)
        if batch_id is None:
            return None

        return {
            "id": batch_id,
            "filename": self.table_extractions.item(current_row, 1).text()
            if self.table_extractions.item(current_row, 1) else "",
            "page_range": self.table_extractions.item(current_row, 2).text()
            if self.table_extractions.item(current_row, 2) else "",
            "timestamp": self.table_extractions.item(current_row, 3).text()
            if self.table_extractions.item(current_row, 3) else "",
        }

    def update_metrics(self):
        stats = get_database_stats()
        self.lbl_total_batches.setText(str(stats["total_batches"]))
        self.lbl_total_questions.setText(str(stats["total_questions"]))
        self.lbl_total_revised.setText(str(stats["total_revised"]))
        self.lbl_total_pending.setText(str(stats["total_unrevised"]))

    def update_action_buttons(self):
        has_selection = self.selected_batch_id is not None
        busy = self.current_worker is not None

        self.btn_delete_batch.setEnabled(has_selection and not busy)
        self.btn_export_batch.setEnabled(has_selection and not busy)
        self.btn_purge_questions.setEnabled(not busy)
        self.btn_nuke_database.setEnabled(not busy)
        self.btn_refresh.setEnabled(not busy)

    def _set_status(self, text):
        self.lbl_status.setText(text)

    def _start_worker(self, action, payload=None):
        if self.current_worker is not None:
            QMessageBox.information(
                self,
                "Busy",
                "A database maintenance job is already running."
            )
            return

        self.current_worker = DatabaseAdminWorker(action, payload)
        self.current_worker.result_ready.connect(self._handle_worker_result)
        self.current_worker.error_occurred.connect(self._handle_worker_error)
        self.current_worker.finished.connect(self._cleanup_worker)
        self.update_action_buttons()
        self._set_status(f"Running: {action.replace('_', ' ').title()}...")
        self.current_worker.start()

    def _cleanup_worker(self):
        self.current_worker = None
        self.update_action_buttons()

    def _handle_worker_error(self, action, message):
        self._set_status(f"Error while running {action.replace('_', ' ')}: {message}")
        QMessageBox.critical(
            self,
            "Database Maintenance Error",
            message
        )

    def _handle_worker_result(self, action, result):
        if action == "export_batch":
            self._set_status(
                f"Exported batch {result['batch_id']} to {os.path.basename(result['save_path'])}"
            )
            QMessageBox.information(
                self,
                "Export Complete",
                f"Batch exported successfully to:\n{result['save_path']}"
            )
            return

        if action == "delete_batch":
            self._set_status(
                f"Deleted batch {result['extraction_id']} and {result['questions_deleted']} child questions."
            )
            QMessageBox.information(
                self,
                "Batch Deleted",
                f"Deleted batch {result['extraction_id']} and {result['questions_deleted']} child questions."
            )
        elif action == "purge_questions":
            self._set_status(
                f"Purged {result['questions_deleted']} questions while preserving batch logs."
            )
            QMessageBox.information(
                self,
                "Purge Complete",
                f"Purged {result['questions_deleted']} questions while keeping the extraction logs."
            )
        elif action == "nuke_database":
            self._set_status(
                f"Database reset. Removed {result['batches_deleted']} batches and {result['questions_deleted']} questions."
            )
            QMessageBox.information(
                self,
                "Database Reset",
                "The database has been cleared and re-initialized."
            )

        self.selected_batch_id = None
        self.refresh_dashboard()
        self.database_mutated.emit()

    def delete_selected_batch(self):
        batch = self._get_selected_batch_record()
        if batch is None:
            QMessageBox.warning(self, "No Selection", "Select a batch first.")
            return

        reply = QMessageBox.warning(
            self,
            "Delete Batch",
            "This will delete the selected batch and all child questions.\n\n"
            f"Batch ID: {batch['id']}\n"
            f"Filename: {batch['filename']}\n"
            f"Page Range: {batch['page_range']}\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._start_worker("delete_batch", {"extraction_id": batch["id"]})

    def export_selected_batch(self):
        batch = self._get_selected_batch_record()
        if batch is None:
            QMessageBox.warning(self, "No Selection", "Select a batch first.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Batch Template",
            f"batch_{batch['id']}.txt",
            "Text Files (*.txt)"
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".txt"):
            save_path += ".txt"

        self._start_worker(
            "export_batch",
            {
                "extraction_id": batch["id"],
                "save_path": save_path,
            }
        )

    def purge_all_questions(self):
        reply = QMessageBox.warning(
            self,
            "Purge All Questions",
            "This will truncate the questions table but keep the extraction logs.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._start_worker("purge_questions")

    def nuke_entire_database(self):
        typed_text, accepted = QInputDialog.getText(
            self,
            "Dangerous Action",
            "Type CONFIRM to clear the database:"
        )
        if not accepted or typed_text.strip().upper() != "CONFIRM":
            return

        reply = QMessageBox.warning(
            self,
            "Nuke Entire Database",
            "This will delete all extraction logs and all questions, then rebuild the empty schema.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._start_worker("nuke_database")

    def open_selected_batch_in_editor(self, row, column):
        batch_item = self.table_extractions.item(row, 0)
        if batch_item is None:
            return

        batch_id = batch_item.data(Qt.ItemDataRole.UserRole)
        if batch_id is None:
            return

        self.batch_open_requested.emit(batch_id)
