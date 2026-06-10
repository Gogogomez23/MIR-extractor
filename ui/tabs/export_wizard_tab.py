from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.export_format import render_export_document
from core.database import (
    count_filtered_questions,
    get_extractions,
    get_filtered_questions,
    get_unique_specialties,
)


def format_batch_label(batch):
    filename = batch.get("filename") or "Unnamed batch"
    page_range = batch.get("page_range") or "-"
    timestamp = batch.get("timestamp") or ""
    return f"Batch #{batch['id']} | {filename} | Pages {page_range} | {timestamp}"


def build_export_document(
    questions,
    filters,
    sorting_mode,
    layout_options,
    include_header=False,
    header_lines=None,
):
    return render_export_document(
        questions,
        include_header=include_header,
        header_title="Custom Export Summary",
        header_details=header_lines,
    )


class ExportDocumentWorker(QThread):
    completed = pyqtSignal(str, int)
    failed = pyqtSignal(str)

    def __init__(self, save_path, filters, sorting_mode, layout_options, include_header=False, header_lines=None):
        super().__init__()
        self.save_path = save_path
        self.filters = dict(filters or {})
        self.sorting_mode = sorting_mode
        self.layout_options = dict(layout_options or {})
        self.include_header = include_header
        self.header_lines = list(header_lines or [])

    def run(self):
        try:
            questions = get_filtered_questions(self.filters, self.sorting_mode)
            header_lines = list(self.header_lines)
            if self.include_header:
                header_lines = [f"Question Count: {len(questions)}"] + header_lines
            content = build_export_document(
                questions,
                self.filters,
                self.sorting_mode,
                self.layout_options,
                include_header=self.include_header,
                header_lines=header_lines,
            )
            with open(self.save_path, "w", encoding="utf-8") as handle:
                handle.write(content)
            self.completed.emit(self.save_path, len(questions))
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWizardTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_worker = None
        self.init_ui()
        self.refresh_filter_sources()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Export Wizard")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        filter_group = QGroupBox("Filter Scope")
        filter_form = QFormLayout(filter_group)

        self.combo_batch_filter = QComboBox()
        self.combo_batch_filter.currentIndexChanged.connect(self.handle_filter_change)
        filter_form.addRow("Batch Filter:", self.combo_batch_filter)

        year_row = QHBoxLayout()
        self.entry_year_start = QLineEdit()
        self.entry_year_start.setPlaceholderText("Any")
        self.entry_year_start.setMaximumWidth(100)
        self.entry_year_start.setValidator(QIntValidator(1900, 2100, self))
        self.entry_year_start.textChanged.connect(self.handle_filter_change)
        year_row.addWidget(self.entry_year_start)
        year_row.addWidget(QLabel("to"))
        self.entry_year_end = QLineEdit()
        self.entry_year_end.setPlaceholderText("Any")
        self.entry_year_end.setMaximumWidth(100)
        self.entry_year_end.setValidator(QIntValidator(1900, 2100, self))
        self.entry_year_end.textChanged.connect(self.handle_filter_change)
        year_row.addWidget(self.entry_year_end)
        year_row.addStretch()
        filter_form.addRow("Year Range:", year_row)

        self.combo_specialty_filter = QComboBox()
        self.combo_specialty_filter.currentIndexChanged.connect(self.handle_filter_change)
        filter_form.addRow("Subject/Specialty Filter:", self.combo_specialty_filter)

        self.combo_review_filter = QComboBox()
        self.combo_review_filter.addItem("All Items", "all")
        self.combo_review_filter.addItem("Only Revised (🟢 OK)", "revised")
        self.combo_review_filter.addItem("Pending Review (🟡/🔴)", "pending")
        self.combo_review_filter.currentIndexChanged.connect(self.handle_filter_change)
        filter_form.addRow("Review Status Filter:", self.combo_review_filter)

        layout.addWidget(filter_group)

        layout_group = QGroupBox("Sorting & Layout Structure")
        layout_form = QFormLayout(layout_group)

        self.combo_sorting = QComboBox()
        self.combo_sorting.addItem("Chronological (ID)", "id")
        self.combo_sorting.addItem("By Exam Year", "year")
        self.combo_sorting.addItem("By Topic (Tema)", "tema")
        self.combo_sorting.addItem("By Question Number", "num")
        self.combo_sorting.currentIndexChanged.connect(self.handle_filter_change)
        layout_form.addRow("Primary Order Dropdown:", self.combo_sorting)

        self.chk_year_headings = QCheckBox("Insert Heading separators between Years")
        self.chk_year_headings.stateChanged.connect(self.handle_filter_change)
        layout_form.addRow(self.chk_year_headings)

        self.chk_tema_blocks = QCheckBox("Group by Tema blocks")
        self.chk_tema_blocks.stateChanged.connect(self.handle_filter_change)
        layout_form.addRow(self.chk_tema_blocks)

        layout.addWidget(layout_group)

        action_group = QGroupBox("Export Action")
        action_layout = QVBoxLayout(action_group)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet("color: #2563eb; font-weight: bold;")
        action_layout.addWidget(self.lbl_summary)

        self.chk_include_header = QCheckBox("Include export header")
        self.chk_include_header.stateChanged.connect(self.handle_filter_change)
        action_layout.addWidget(self.chk_include_header)

        self.btn_generate = QPushButton("Generate Custom Document")
        self.btn_generate.setStyleSheet("background-color: #1d4ed8; color: white; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_custom_document)
        action_layout.addWidget(self.btn_generate)

        layout.addWidget(action_group)
        layout.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_filter_sources()

    def refresh_filter_sources(self):
        current_batch = self.combo_batch_filter.currentData()
        current_specialty = self.combo_specialty_filter.currentData()

        batches = get_extractions()
        specialties = get_unique_specialties()

        self.combo_batch_filter.blockSignals(True)
        self.combo_specialty_filter.blockSignals(True)
        try:
            self.combo_batch_filter.clear()
            self.combo_batch_filter.addItem("All Batches", None)
            for batch in batches:
                self.combo_batch_filter.addItem(format_batch_label(batch), batch["id"])

            self.combo_specialty_filter.clear()
            self.combo_specialty_filter.addItem("All Specialties", None)
            for specialty in specialties:
                self.combo_specialty_filter.addItem(specialty, specialty)

            self._restore_combo_selection(self.combo_batch_filter, current_batch, default_index=0)
            self._restore_combo_selection(self.combo_specialty_filter, current_specialty, default_index=0)
        finally:
            self.combo_batch_filter.blockSignals(False)
            self.combo_specialty_filter.blockSignals(False)

        self.update_summary_label()

    def refresh_data_sources(self):
        self.refresh_filter_sources()

    def _restore_combo_selection(self, combo, target_value, default_index=0):
        if target_value is None:
            combo.setCurrentIndex(default_index)
            return

        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(default_index)

    def handle_filter_change(self, *args):
        self.update_summary_label()

    def _collect_filters(self):
        batch_id = self.combo_batch_filter.currentData()
        specialty = self.combo_specialty_filter.currentData()
        review_status = self.combo_review_filter.currentData()

        year_start_text = self.entry_year_start.text().strip()
        year_end_text = self.entry_year_end.text().strip()

        year_start = None
        year_end = None
        if year_start_text:
            year_start = self._parse_year_value(year_start_text)
            if year_start is None:
                return None, "Enter a valid start year or leave the field blank."
        if year_end_text:
            year_end = self._parse_year_value(year_end_text)
            if year_end is None:
                return None, "Enter a valid end year or leave the field blank."

        if year_start is not None and year_end is not None and year_start > year_end:
            return None, "Start year cannot be greater than end year."

        filters = {
            "batch_id": batch_id,
            "year_start": year_start,
            "year_end": year_end,
            "specialty": specialty,
            "review_status": review_status,
        }
        return filters, None

    def _parse_year_value(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _current_sorting_mode(self):
        return self.combo_sorting.currentData() or "id"

    def _current_layout_options(self):
        return {
            "insert_year_headings": self.chk_year_headings.isChecked(),
            "group_by_tema": self.chk_tema_blocks.isChecked(),
        }

    def _format_year_range_label(self):
        start_text = self.entry_year_start.text().strip() or "Any"
        end_text = self.entry_year_end.text().strip() or "Any"
        if start_text == "Any" and end_text == "Any":
            return "Any"
        return f"{start_text} to {end_text}"

    def _build_header_lines(self):
        return [
            "Source: Export Wizard",
            f"Batch Filter: {self.combo_batch_filter.currentText()}",
            f"Year Range: {self._format_year_range_label()}",
            f"Specialty Filter: {self.combo_specialty_filter.currentText()}",
            f"Review Status Filter: {self.combo_review_filter.currentText()}",
            f"Primary Order: {self.combo_sorting.currentText()}",
        ]

    def update_summary_label(self):
        filters, error = self._collect_filters()

        if error:
            self.lbl_summary.setText(error)
            self.lbl_summary.setStyleSheet("color: #b91c1c; font-weight: bold;")
            return

        count = count_filtered_questions(filters)
        sorting_label = self.combo_sorting.currentText()
        if count == 0:
            self.lbl_summary.setText(
                f"No questions match the active filter criteria. Sorting: {sorting_label}."
            )
        else:
            self.lbl_summary.setText(
                f"Ready to export: {count} questions match your active filter criteria. "
                f"Sorting: {sorting_label}. "
                f"Header: {'On' if self.chk_include_header.isChecked() else 'Off'}."
            )

        self.lbl_summary.setStyleSheet("color: #2563eb; font-weight: bold;")

    def _set_busy(self, busy):
        self.btn_generate.setEnabled(not busy)
        self.combo_batch_filter.setEnabled(not busy)
        self.entry_year_start.setEnabled(not busy)
        self.entry_year_end.setEnabled(not busy)
        self.combo_specialty_filter.setEnabled(not busy)
        self.combo_review_filter.setEnabled(not busy)
        self.combo_sorting.setEnabled(not busy)
        self.chk_year_headings.setEnabled(not busy)
        self.chk_tema_blocks.setEnabled(not busy)
        self.chk_include_header.setEnabled(not busy)

    def generate_custom_document(self):
        filters, error = self._collect_filters()
        if error:
            QMessageBox.warning(self, "Filter Validation", error)
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Custom Document",
            "custom_export.txt",
            "Text Files (*.txt)"
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".txt"):
            save_path += ".txt"

        if self.current_worker is not None:
            QMessageBox.information(self, "Busy", "An export job is already running.")
            return

        self.current_worker = ExportDocumentWorker(
            save_path=save_path,
            filters=filters,
            sorting_mode=self._current_sorting_mode(),
            layout_options=self._current_layout_options(),
            include_header=self.chk_include_header.isChecked(),
            header_lines=self._build_header_lines(),
        )
        self.current_worker.completed.connect(self.handle_export_success)
        self.current_worker.failed.connect(self.handle_export_failure)
        self.current_worker.finished.connect(self._cleanup_worker)
        self._set_busy(True)
        self.current_worker.start()

    def _cleanup_worker(self):
        self.current_worker = None
        self._set_busy(False)
        self.update_summary_label()

    def handle_export_success(self, save_path, count):
        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {count} questions to:\n{save_path}"
        )

    def handle_export_failure(self, message):
        QMessageBox.critical(
            self,
            "Export Error",
            f"Could not generate the custom document:\n{message}"
        )
