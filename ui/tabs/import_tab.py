import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QFormLayout, QGroupBox, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QFileDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QComboBox)
from core.export_format import render_quick_export_text
from ui.workers import PDFParseWorker, parse_year_filter_bounds
from core.database import save_questions, get_all_questions, get_latest_extraction_id
import pdfplumber

class ImportTab(QWidget):
    question_selected_for_edit = pyqtSignal(dict)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.pdf_path = ""
        self.current_batch_id = None
        self.current_questions = []
        self.current_intake_settings = {
            "year_filter_text": "",
            "ignore_images": False,
            "duplicate_policy": "allow_tag",
        }
        self._stored_page_values = ("6", "6")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.current_start_page = 0
        self.current_end_page = 0

        # File Select Area
        file_layout = QHBoxLayout()
        self.btn_browse = QPushButton("Select Book PDF")
        self.btn_browse.clicked.connect(self.browse_file)
        self.lbl_file = QLabel("No file selected")
        file_layout.addWidget(self.btn_browse)
        file_layout.addWidget(self.lbl_file, 1)
        layout.addLayout(file_layout)

        # Range Control Controls
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Start Page:"))
        self.entry_start = QLineEdit("6")
        self.entry_start.setFixedWidth(50)
        control_layout.addWidget(self.entry_start)

        control_layout.addWidget(QLabel("End Page:"))
        self.entry_end = QLineEdit("6")
        self.entry_end.setFixedWidth(50)
        control_layout.addWidget(self.entry_end)

        self.chk_process_entire_document = QCheckBox("Process Entire Document")
        self.chk_process_entire_document.toggled.connect(self.handle_process_entire_document_toggled)
        control_layout.addWidget(self.chk_process_entire_document)

        self.btn_extract = QPushButton("Extract Range")
        self.btn_extract.setStyleSheet("background-color: green; color: white;")
        self.btn_extract.clicked.connect(self.start_extraction)
        control_layout.addWidget(self.btn_extract)

        # Grid View Sort Order Filter Dropdown
        control_layout.addWidget(QLabel("View Sorting Mode:"))
        self.combo_sort = QComboBox()
        # use data values so we can pass explicit sorting modes
        self.combo_sort.addItem("Order Added (ID)", "id")
        self.combo_sort.addItem("Organize by Year", "year")
        self.combo_sort.addItem("Organize by Question Number", "num")
        self.combo_sort.addItem("Organize by Topic", "tema")
        self.combo_sort.currentIndexChanged.connect(self.load_table_data)
        control_layout.addWidget(self.combo_sort)

        control_layout.addWidget(QLabel("Direction:"))
        self.combo_sort_dir = QComboBox()
        self.combo_sort_dir.addItem("Descending", "desc")
        self.combo_sort_dir.addItem("Ascending", "asc")
        # keep prior default ordering behavior (ascending primary order)
        self.combo_sort_dir.setCurrentIndex(1)
        self.combo_sort_dir.currentIndexChanged.connect(self.load_table_data)
        control_layout.addWidget(self.combo_sort_dir)

        self.btn_export = QPushButton("Quick Export (Current Batch)")
        self.btn_export.setEnabled(False)
        self.btn_export.setToolTip("Export only the most recently extracted batch.")
        self.btn_export.clicked.connect(self.export_document)
        control_layout.addWidget(self.btn_export)
        layout.addLayout(control_layout)

        filter_group = QGroupBox("Intake Validation Filters")
        filter_form = QFormLayout(filter_group)

        self.entry_year_filter = QLineEdit()
        self.entry_year_filter.setPlaceholderText("e.g., 2022 or 2018-2022")
        self.entry_year_filter.setMaximumWidth(170)
        filter_form.addRow("Year Filter:", self.entry_year_filter)

        self.chk_ignore_images = QCheckBox("Ignore questions with images")
        filter_form.addRow("", self.chk_ignore_images)

        self.combo_duplicate_policy = QComboBox()
        self.combo_duplicate_policy.addItem("Allow & Tag as Duplicate", "allow_tag")
        self.combo_duplicate_policy.addItem("Skip Automatically", "skip")
        self.combo_duplicate_policy.addItem("Overwrite Existing Record", "overwrite")
        filter_form.addRow("Duplicate Handling Policy:", self.combo_duplicate_policy)

        layout.addWidget(filter_group)

        # Questions Display Grid Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Año", "Nº Pregunta", "Topic / Specialty", "Enunciado Preview", "RC"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellDoubleClicked.connect(self.handle_row_double_click)
        layout.addWidget(self.table)

        self.load_table_data()

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Book PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.lbl_file.setText(os.path.basename(file_path))
            if self.chk_process_entire_document.isChecked():
                self._sync_full_document_page_range_preview()

    def handle_process_entire_document_toggled(self, checked):
        if checked:
            self._stored_page_values = (self.entry_start.text(), self.entry_end.text())
            self.entry_start.setEnabled(False)
            self.entry_end.setEnabled(False)
            self._sync_full_document_page_range_preview()
            return

        self.entry_start.setEnabled(True)
        self.entry_end.setEnabled(True)
        start_value, end_value = self._stored_page_values
        if start_value:
            self.entry_start.setText(start_value)
        if end_value:
            self.entry_end.setText(end_value)

    def _get_pdf_page_count(self, show_error=True):
        if not self.pdf_path:
            return None

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                return len(pdf.pages)
        except Exception as exc:
            if show_error:
                QMessageBox.critical(
                    self,
                    "PDF Error",
                    f"Could not read the selected PDF document:\n{exc}"
                )
            return None

    def _sync_full_document_page_range_preview(self):
        total_doc_pages = self._get_pdf_page_count(show_error=False)
        if not total_doc_pages:
            return

        self.entry_start.setText("1")
        self.entry_end.setText(str(total_doc_pages))

    def _collect_intake_settings(self):
        year_text = self.entry_year_filter.text().strip()
        try:
            parse_year_filter_bounds(year_text)
        except ValueError as exc:
            return None, str(exc)

        duplicate_policy = self.combo_duplicate_policy.currentData() or "allow_tag"

        return {
            "year_filter_text": year_text,
            "ignore_images": self.chk_ignore_images.isChecked(),
            "duplicate_policy": duplicate_policy,
        }, None

    def start_extraction(self):
        if not self.pdf_path:
            QMessageBox.critical(self, "Error", "Please load a PDF document first.")
            return

        intake_settings, validation_error = self._collect_intake_settings()
        if validation_error:
            QMessageBox.critical(self, "Error", validation_error)
            return

        total_doc_pages = self._get_pdf_page_count()
        if total_doc_pages is None:
            return

        if self.chk_process_entire_document.isChecked():
            start_p = 1
            end_p = total_doc_pages
            self.entry_start.setText(str(start_p))
            self.entry_end.setText(str(end_p))
        else:
            try:
                start_p = int(self.entry_start.text())
                end_p = int(self.entry_end.text())
            except ValueError:
                QMessageBox.critical(self, "Error", "Page arguments must be whole numbers.")
                return

        # Requirement: Throw a soft alert warning if user entry exceeds document bounds
        if start_p < 1:
            QMessageBox.critical(self, "Error", "Start page must be greater than 0.")
            return
        if start_p > end_p:
            QMessageBox.critical(self, "Error", "Start page cannot exceed end range.")
            return
        if end_p > total_doc_pages:
            reply = QMessageBox.warning(
                self, "Page Range Warning",
                f"You requested page {end_p}, but the PDF only has {total_doc_pages} pages.\n"
                "The application will process up to the absolute last page of the document. Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
            if reply == QMessageBox.StandardButton.No:
                return

        actual_end_page = min(end_p, total_doc_pages)
        self.current_start_page = start_p
        self.current_end_page = actual_end_page
        self.current_intake_settings = intake_settings
        self.main_window.progress_bar.setValue(0)
        self.btn_extract.setEnabled(False)

        # Thread instantiation execution
        self.worker = PDFParseWorker(
            self.pdf_path,
            start_p,
            actual_end_page,
            intake_filters=intake_settings,
        )
        self.worker.progress_updated.connect(self.main_window.progress_bar.setValue)
        self.worker.parsing_complete.connect(self.handle_parse_success)
        self.worker.parsing_error.connect(self.handle_parse_failure)
        self.worker.start()

    def handle_parse_success(self, items):
        self.btn_extract.setEnabled(True)
        self.main_window.progress_bar.setValue(100)

        if items:
            try:
                save_result = save_questions(
                    items,
                    filename=os.path.basename(self.pdf_path),
                    page_range=f"{self.current_start_page}-{self.current_end_page}",
                    duplicate_policy=self.current_intake_settings.get("duplicate_policy", "allow_tag")
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Database Write Error",
                    f"Could not commit the filtered batch to SQLite:\n{exc}"
                )
                return

            inserted = save_result.get("inserted_count", 0)
            updated = save_result.get("updated_count", 0)
            skipped = save_result.get("skipped_count", 0)

            if inserted or updated:
                QMessageBox.information(
                    self,
                    "Success",
                    (
                        f"Ingested {len(items)} filtered questions.\n"
                        f"Inserted: {inserted} | Updated: {updated} | Skipped: {skipped}"
                    ),
                )
                if hasattr(self.main_window, "handle_database_mutation"):
                    self.main_window.handle_database_mutation()
                else:
                    self.load_table_data()
            else:
                QMessageBox.information(
                    self,
                    "Ingestion Notice",
                    "The batch matched the intake filters, but the duplicate policy skipped every row."
                )
                self.load_table_data()
        else:
            QMessageBox.warning(self, "Extraction Notice",
                                "No questions matched the active intake filters.")

    def handle_parse_failure(self, err_msg):
        self.btn_extract.setEnabled(True)
        QMessageBox.critical(self, "Parsing Error", f"An internal exception stopped the parsing routine:\n{err_msg}")

    def load_table_data(self, *args):
        self.current_batch_id = get_latest_extraction_id()
        if self.current_batch_id is None:
            self.current_questions = []
            self.table.setUpdatesEnabled(False)
            self.table.blockSignals(True)
            try:
                self.table.clearContents()
                self.table.setRowCount(0)
                self.btn_export.setEnabled(False)
            finally:
                self.table.blockSignals(False)
                self.table.setUpdatesEnabled(True)
            return

        # prefer explicit data-driven sorting mode + direction when available
        sorting_mode = self.combo_sort.currentData() or "id"
        sorting_dir = getattr(self, "combo_sort_dir", None) and self.combo_sort_dir.currentData() or "desc"
        questions = get_all_questions(
            extraction_id=self.current_batch_id,
            sorting_mode=sorting_mode,
            sorting_dir=sorting_dir
        )
        self.current_questions = list(questions)

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(0)
            if not questions:
                self.btn_export.setEnabled(False)
                return

            self.btn_export.setEnabled(True)
            for idx, q in enumerate(questions):
                self.table.insertRow(idx)

                status_text = q["status"] or "Unknown"
                status_item = QTableWidgetItem(status_text)
                status_item.setData(Qt.ItemDataRole.UserRole, q["id"])
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                year_item = QTableWidgetItem(str(q["ano"] or ""))
                year_item.setFlags(year_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                num_item = QTableWidgetItem(str(q["num"] or ""))
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                meta_item = QTableWidgetItem(
                    f"{(q['especialidad'] or '')[:24]} | {(q['tema'] or '')[:24]}"
                )
                meta_item.setToolTip(
                    f"Specialty: {q.get('especialidad') or ''}\nTema: {q.get('tema') or ''}"
                )
                meta_item.setFlags(meta_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                stem_preview = q["enunciado"] or ""
                if len(stem_preview) > 50:
                    stem_preview = stem_preview[:50] + "..."
                stem_item = QTableWidgetItem(stem_preview)
                stem_item.setFlags(stem_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                rc_item = QTableWidgetItem(str(q["rc"] or ""))
                rc_item.setFlags(rc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(idx, 0, status_item)
                self.table.setItem(idx, 1, year_item)
                self.table.setItem(idx, 2, num_item)
                self.table.setItem(idx, 3, meta_item)
                self.table.setItem(idx, 4, stem_item)
                self.table.setItem(idx, 5, rc_item)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def handle_row_double_click(self, row, column):
        if row < 0 or row >= len(self.current_questions):
            return

        target_q = dict(self.current_questions[row])
        target_q["opciones"] = list(target_q.get("opciones", []))
        self.question_selected_for_edit.emit(target_q)

    def export_document(self):
        if not self.current_questions:
            self.load_table_data()

        if not self.current_questions:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Export File Location", "", "Text Files (*.txt)")
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(render_quick_export_text(self.current_questions))
            QMessageBox.information(self, "Success", f"Document generated at:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed saving output file down: {str(e)}")
