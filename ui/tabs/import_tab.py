from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QFileDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QComboBox)
from PyQt6.QtCore import pyqtSignal
from ui.workers import PDFParseWorker
from core.database import save_questions, get_all_questions
import pdfplumber


class ImportTab(QWidget):
    question_selected_for_edit = pyqtSignal(dict)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.pdf_path = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

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

        self.btn_export = QPushButton("Export Template Doc")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_document)
        control_layout.addWidget(self.btn_export)
        layout.addLayout(control_layout)

        # Questions Display Grid Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Reference", "Topic / Specialty", "Enunciado Preview", "Options Count", "RC"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

        self.main_window.progress_bar.setValue(0)
        self.btn_extract.setEnabled(False)

        # Thread instantiation execution
        self.worker = PDFParseWorker(self.pdf_path, start_p, end_p)
        self.worker.progress_updated.connect(self.main_window.progress_bar.setValue)
        self.worker.parsing_complete.connect(self.handle_parse_success)
        self.worker.parsing_error.connect(self.handle_parse_failure)
        self.worker.start()

    def handle_parse_success(self, items):
        self.btn_extract.setEnabled(True)
        self.main_window.progress_bar.setValue(100)

        if items:
            save_questions(items)
            QMessageBox.information(self, "Success",
                                    f"Successfully extracted and saved {len(items)} questions to Database!")
            self.load_table_data()
        else:
            QMessageBox.warning(self, "Extraction Notice",
                                "No structural layout items matches found in target page range bounds.")

    def handle_parse_failure(self, err_msg):
        self.btn_extract.setEnabled(True)
        QMessageBox.critical(self, "Parsing Error", f"An internal exception stopped the parsing routine:\n{err_msg}")

    def load_table_data(self):
        sort_by_year = (self.combo_sort.currentIndex() == 1)
        questions = get_all_questions(sort_by_year=sort_by_year)

        self.table.setRowCount(0)
        if not questions:
            self.btn_export.setEnabled(False)
            return

        self.btn_export.setEnabled(True)
        for idx, q in enumerate(questions):
            self.table.insertRow(idx)

            status_item = QTableWidgetItem(q["status"])
            ref_item = QTableWidgetItem(f"MIR {q['ano']} - Q{q['num']}")
            meta_item = QTableWidgetItem(f"T: {q['tema'][:15]}...\nS: {q['especialidad'][:15]}")
            stem_item = QTableWidgetItem(q["enunciado"][:50] + "...")
            opts_item = QTableWidgetItem(f"{len(q['opciones'])} Options")
            rc_item = QTableWidgetItem(f"RC: {q['rc']}")

            # Save the database index primary key directly inside row item memory metadata
            status_item.setData(32, q["id"])

            self.table.setItem(idx, 0, status_item)
            self.table.setItem(idx, 1, ref_item)
            self.table.setItem(idx, 2, meta_item)
            self.table.setItem(idx, 3, stem_item)
            self.table.setItem(idx, 4, opts_item)
            self.table.setItem(idx, 5, rc_item)

    def handle_row_double_click(self, row, column):
        q_id = self.table.item(row, 0).data(32)
        questions = get_all_questions()
        target_q = next((q for q in questions if q["id"] == q_id), None)
        if target_q:
            self.question_selected_for_edit.emit(target_q)

    def export_document(self):
        questions = get_all_questions()
        if not questions:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Export File Location", "", "Text Files (*.txt)")
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                for q in questions:
                    f.write(f"Enunciado: {q['enunciado']}\n\n")
                    f.write("Opciones:\n")
                    for i, opt in enumerate(q['opciones'], 1):
                        f.write(f"    {i}. {opt}\n")
                    f.write(f"\nRC: {q['rc']}\n\n")
                    f.write(
                        f"Tema: {q['tema']} | Especialidad: {q['especialidad']} | Dificultad: {q['dificultad']} | Año: {q['ano']}\n\n")
                    f.write(f"Explicación:\n{q['explicacion']}\n")
                    f.write("_________________________________________________________________________________\n\n")
            QMessageBox.information(self, "Success", f"Document generated at:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed saving output file down: {str(e)}")


import os
