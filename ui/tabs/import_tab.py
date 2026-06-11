import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QFileDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QComboBox)
from core.export_format import render_quick_export_text
from ui.workers import PDFParseWorker
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

        self.btn_extract = QPushButton("Extract Range")
        self.btn_extract.setStyleSheet("background-color: green; color: white;")
        self.btn_extract.clicked.connect(self.start_extraction)
        control_layout.addWidget(self.btn_extract)

        # Grid View Sort Order Filter Dropdown
        control_layout.addWidget(QLabel("View Sorting Mode:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Order Added (ID)", "Organize by Year"])
        self.combo_sort.currentIndexChanged.connect(self.load_table_data)
        control_layout.addWidget(self.combo_sort)

        self.btn_export = QPushButton("Quick Export (Current Batch)")
        self.btn_export.setEnabled(False)
        self.btn_export.setToolTip("Export only the most recently extracted batch.")
        self.btn_export.clicked.connect(self.export_document)
        control_layout.addWidget(self.btn_export)
        layout.addLayout(control_layout)

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

    def start_extraction(self):
        if not self.pdf_path:
            QMessageBox.critical(self, "Error", "Please load a PDF document first.")
            return

        try:
            start_p = int(self.entry_start.text())
            end_p = int(self.entry_end.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Page arguments must be whole numbers.")
            return

        with pdfplumber.open(self.pdf_path) as pdf:
            total_doc_pages = len(pdf.pages)

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
        self.main_window.progress_bar.setValue(0)
        self.btn_extract.setEnabled(False)

        # Thread instantiation execution
        self.worker = PDFParseWorker(self.pdf_path, start_p, actual_end_page)
        self.worker.progress_updated.connect(self.main_window.progress_bar.setValue)
        self.worker.parsing_complete.connect(self.handle_parse_success)
        self.worker.parsing_error.connect(self.handle_parse_failure)
        self.worker.start()

    def handle_parse_success(self, items):
        self.btn_extract.setEnabled(True)
        self.main_window.progress_bar.setValue(100)

        if items:
            save_questions(
                items,
                filename=os.path.basename(self.pdf_path),
                page_range=f"{self.current_start_page}-{self.current_end_page}"
            )
            QMessageBox.information(self, "Success",
                                    f"Successfully extracted and saved {len(items)} questions to Database!")
            if hasattr(self.main_window, "handle_database_mutation"):
                self.main_window.handle_database_mutation()
            else:
                self.load_table_data()
        else:
            QMessageBox.warning(self, "Extraction Notice",
                                "No structural layout items matches found in target page range bounds.")

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

        sort_by_year = (self.combo_sort.currentIndex() == 1)
        questions = get_all_questions(
            extraction_id=self.current_batch_id,
            sort_by_year=sort_by_year,
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
