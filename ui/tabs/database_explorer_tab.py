from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import get_extractions, get_explorer_questions


def format_batch_label(batch):
    filename = batch.get("filename") or "Unnamed batch"
    page_range = batch.get("page_range") or "-"
    timestamp = batch.get("timestamp") or ""
    return f"Batch #{batch['id']} | {filename} | Pages {page_range} | {timestamp}"


class DatabaseExplorerWorker(QThread):
    loaded = pyqtSignal(int, list)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id, filters):
        super().__init__()
        self.request_id = request_id
        self.filters = dict(filters or {})

    def run(self):
        try:
            questions = get_explorer_questions(self.filters)
            self.loaded.emit(self.request_id, questions)
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))


class DatabaseExplorerTab(QWidget):
    question_selected_for_edit = pyqtSignal(dict)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_worker = None
        self._pending_refresh = False
        self._load_request_id = 0
        self.current_questions = []
        self.selected_question_id = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title = QLabel("Database Explorer")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        header_row.addWidget(title)
        header_row.addStretch()

        self.btn_refresh = QPushButton("Refresh View")
        self.btn_refresh.clicked.connect(self.refresh_data_views)
        header_row.addWidget(self.btn_refresh)
        layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Batch Filter:"))

        self.combo_batch_filter = QComboBox()
        self.combo_batch_filter.currentIndexChanged.connect(self.handle_filter_change)
        filter_row.addWidget(self.combo_batch_filter, 1)

        filter_row.addWidget(QLabel("View Sorting Modes"))
        self.combo_sort_view = QComboBox()
        # add items with explicit internal data values that match database sorting modes
        self.combo_sort_view.addItem("Order Added (ID)", "id")
        self.combo_sort_view.addItem("Organize by Year", "year")
        self.combo_sort_view.addItem("Organize by Question Number", "num")
        self.combo_sort_view.addItem("Organize by Topic", "tema")
        self.combo_sort_view.currentIndexChanged.connect(self.handle_filter_change)
        filter_row.addWidget(self.combo_sort_view)
        # Sorting direction selector (descending by default)
        self.combo_sort_dir = QComboBox()
        self.combo_sort_dir.addItem("Descending", "desc")
        self.combo_sort_dir.addItem("Ascending", "asc")
        # keep prior default behavior (primary ordering ascending) by selecting Ascending
        self.combo_sort_dir.setCurrentIndex(1)
        self.combo_sort_dir.currentIndexChanged.connect(self.handle_filter_change)
        filter_row.addWidget(self.combo_sort_dir)

        filter_row.addWidget(QLabel("Revision Filter:"))
        self.combo_revision_filter = QComboBox()
        self.combo_revision_filter.addItem("All Statuses", "all")
        self.combo_revision_filter.addItem("Revised Only", "revised")
        self.combo_revision_filter.addItem("Unrevised Only", "unrevised")
        self.combo_revision_filter.currentIndexChanged.connect(self.handle_filter_change)
        filter_row.addWidget(self.combo_revision_filter)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Revised Status",
                "Status Flag",
                "Año",
                "Nº Pregunta",
                "Specialty/Tema",
                "Enunciado Preview",
                "RC",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.table.cellDoubleClicked.connect(self.handle_row_double_click)
        layout.addWidget(self.table)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color: #4b5563;")
        layout.addWidget(self.lbl_status)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_data_sources()

    def refresh_data_sources(self):
        self.refresh_filter_sources()
        self.refresh_data_views()

    def refresh_filter_sources(self):
        current_batch = self.combo_batch_filter.currentData()
        batches = get_extractions()

        self.combo_batch_filter.blockSignals(True)
        try:
            self.combo_batch_filter.clear()
            self.combo_batch_filter.addItem("All Questions", None)
            for batch in batches:
                self.combo_batch_filter.addItem(format_batch_label(batch), batch["id"])
            self._restore_combo_selection(self.combo_batch_filter, current_batch, default_index=0)
        finally:
            self.combo_batch_filter.blockSignals(False)

    def refresh_data_views(self, *args):
        if self.current_worker is not None:
            self._pending_refresh = True
            self._load_request_id += 1
            return

        self._pending_refresh = False
        self._load_request_id += 1
        request_id = self._load_request_id
        filters = self._collect_filters()

        self._set_busy(True)
        self.current_worker = DatabaseExplorerWorker(request_id, filters)
        self.current_worker.loaded.connect(self._handle_worker_loaded)
        self.current_worker.failed.connect(self._handle_worker_failed)
        self.current_worker.finished.connect(self._handle_worker_finished)
        self.current_worker.start()

    def _collect_filters(self):
        return {
            "batch_id": self.combo_batch_filter.currentData(),
            "review_status": self.combo_revision_filter.currentData(),
            "sorting_mode": self.combo_sort_view.currentData(),
            "sorting_dir": getattr(self, "combo_sort_dir", None) and self.combo_sort_dir.currentData()
        }

    def _restore_combo_selection(self, combo, target_value, default_index=0):
        if target_value is None:
            combo.setCurrentIndex(default_index)
            return

        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(default_index)

    def _set_busy(self, busy):
        self.combo_batch_filter.setEnabled(not busy)
        self.combo_revision_filter.setEnabled(not busy)
        self.btn_refresh.setEnabled(not busy)
        if busy:
            self.lbl_status.setText("Loading database history...")

    def _format_status_flag(self, status_text):
        normalized = (status_text or "").upper()
        if "🟢" in normalized or "OK" in normalized:
            return "🟢"
        if "🔴" in normalized or "ERROR" in normalized:
            return "🔴"
        if "🟡" in normalized or "REVIEW" in normalized or "DUPLICATE" in normalized:
            return "🟡"
        return "🟡"

    def _truncate_preview(self, text, limit=80):
        value = text or ""
        if len(value) <= limit:
            return value
        return value[:limit - 3] + "..."

    def _copy_question(self, question):
        payload = dict(question)
        payload["opciones"] = list(question.get("opciones", []))
        return payload

    def _render_table(self, questions):
        previous_selected_id = self.selected_question_id
        self.current_questions = list(questions or [])

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(0)

            for row_idx, question in enumerate(self.current_questions):
                self.table.insertRow(row_idx)

                revised = bool(int(question.get("revised", 0) or 0))
                revised_item = QTableWidgetItem("☑" if revised else "☐")
                revised_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                revised_item.setToolTip("Revised" if revised else "Unrevised")
                revised_item.setData(Qt.ItemDataRole.UserRole, question["id"])
                revised_item.setFlags(revised_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                flag_item = QTableWidgetItem(self._format_status_flag(question.get("status")))
                flag_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                flag_item.setToolTip(question.get("status_msg") or question.get("status") or "")
                flag_item.setFlags(flag_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                year_item = QTableWidgetItem(str(question.get("ano") or ""))
                year_item.setFlags(year_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                num_item = QTableWidgetItem(str(question.get("num") or ""))
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                specialty_text = question.get("especialidad") or ""
                tema_text = question.get("tema") or ""
                specialty_item = QTableWidgetItem(f"{specialty_text} | {tema_text}".strip(" |"))
                specialty_item.setToolTip(f"Specialty: {specialty_text}\nTema: {tema_text}")
                specialty_item.setFlags(specialty_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                preview_text = self._truncate_preview(question.get("enunciado") or "")
                preview_item = QTableWidgetItem(preview_text)
                preview_item.setToolTip(question.get("enunciado") or "")
                preview_item.setFlags(preview_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                rc_item = QTableWidgetItem(str(question.get("rc") or ""))
                rc_item.setFlags(rc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row_idx, 0, revised_item)
                self.table.setItem(row_idx, 1, flag_item)
                self.table.setItem(row_idx, 2, year_item)
                self.table.setItem(row_idx, 3, num_item)
                self.table.setItem(row_idx, 4, specialty_item)
                self.table.setItem(row_idx, 5, preview_item)
                self.table.setItem(row_idx, 6, rc_item)

            self._restore_selection(previous_selected_id)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        if not self.current_questions:
            self.lbl_status.setText("No questions match the active filters.")
        else:
            self.lbl_status.setText(f"Loaded {len(self.current_questions)} questions.")

    def _restore_selection(self, target_question_id):
        if target_question_id is None:
            self.table.clearSelection()
            self.selected_question_id = None
            return

        for row_idx, question in enumerate(self.current_questions):
            if question["id"] == target_question_id:
                self.table.selectRow(row_idx)
                self.table.setCurrentCell(row_idx, 0)
                self.selected_question_id = target_question_id
                return

        self.table.clearSelection()
        self.selected_question_id = None

    def _handle_worker_loaded(self, request_id, questions):
        if request_id != self._load_request_id:
            return
        self._render_table(questions)

    def _handle_worker_failed(self, request_id, message):
        if request_id != self._load_request_id:
            return

        self.current_questions = []
        self.table.setRowCount(0)
        self.lbl_status.setText(f"Failed to load questions: {message}")
        QMessageBox.critical(self, "Database Explorer Error", message)

    def _handle_worker_finished(self):
        self.current_worker = None
        self._set_busy(False)
        if self._pending_refresh:
            self._pending_refresh = False
            self.refresh_data_views()

    def handle_filter_change(self, *args):
        self.refresh_data_views()

    def handle_selection_changed(self):
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self.current_questions):
            self.selected_question_id = None
            return
        self.selected_question_id = self.current_questions[current_row]["id"]

    def handle_row_double_click(self, row, column):
        if row < 0 or row >= len(self.current_questions):
            return

        self.question_selected_for_edit.emit(self._copy_question(self.current_questions[row]))
