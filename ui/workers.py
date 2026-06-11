from PyQt6.QtCore import QThread, pyqtSignal
import pdfplumber
import re
from core.parser import clean_text_hyphens, parse_pdf_stream


class PDFParseWorker(QThread):
    progress_updated = pyqtSignal(int)
    parsing_complete = pyqtSignal(list)
    parsing_error = pyqtSignal(str)

    def __init__(self, pdf_path, start_page, end_page, intake_filters=None):
        super().__init__()
        self.pdf_path = pdf_path
        self.start_page = start_page
        self.end_page = end_page
        self.intake_filters = dict(intake_filters or {})

    def _normalize_year_filter(self):
        raw_year = self.intake_filters.get("year")
        if raw_year is None:
            return None

        year_text = str(raw_year).strip()
        if not year_text:
            return None

        try:
            return str(int(year_text))
        except (TypeError, ValueError):
            return None

    def _compile_keyword_pattern(self):
        pattern = str(self.intake_filters.get("keyword_pattern") or "").strip()
        if not pattern:
            return None

        try:
            return re.compile(pattern, re.IGNORECASE)
        except re.error:
            return re.compile(re.escape(pattern), re.IGNORECASE)

    def _question_text_blob(self, question):
        options = question.get("opciones") or []
        parts = [
            question.get("enunciado", ""),
            " ".join(options),
            question.get("explicacion", ""),
            question.get("tema", ""),
            question.get("especialidad", ""),
        ]
        return "\n".join(part for part in parts if part)

    def _matches_intake_filters(self, question, year_filter, keyword_regex):
        if year_filter is not None and str(question.get("ano", "")).strip() != year_filter:
            return False

        if keyword_regex is not None:
            haystack = self._question_text_blob(question)
            if not keyword_regex.search(haystack):
                return False

        return True

    def _apply_intake_filters(self, questions):
        year_filter = self._normalize_year_filter()
        keyword_regex = self._compile_keyword_pattern()
        if year_filter is None and keyword_regex is None:
            return questions

        filtered_questions = []
        for question in questions:
            if self._matches_intake_filters(question, year_filter, keyword_regex):
                filtered_questions.append(question)
        return filtered_questions

    def run(self):
        try:
            current_specialty = "General"
            current_tema = "No identificado"

            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                # Fail-safe check: if the user requested a range larger than the document, cap it cleanly
                actual_end = min(self.end_page, total_pages)
                total_to_process = (actual_end - self.start_page) + 1

                running_text_stream = ""
                steps_completed = 0

                for p_idx in range(self.start_page - 1, actual_end):
                    page = pdf.pages[p_idx]
                    w, h = page.width, page.height

                    header_crop = page.crop((0, 0, w, 45))
                    header_txt = header_crop.extract_text() or ""

                    clean_head = header_txt.replace("Preguntas MIR 2014-2024 y sus comentarios", "").replace(
                        "Libro Gordo AMIR", "")
                    clean_head = re.sub(r'(?i)\basignatura\b', '', clean_head)
                    clean_head = re.sub(r'^[-\s:]+|[-\s:]+$', '', clean_head).strip()

                    if len(clean_head) > 3:
                        current_specialty = clean_head

                    left_box = page.within_bbox((0, 40, w / 2, h))
                    right_box = page.within_bbox((w / 2, 40, w, h))

                    left_txt = clean_text_hyphens(left_box.extract_text() or "")
                    right_txt = clean_text_hyphens(right_box.extract_text() or "")

                    combined_page_txt = left_txt + "\n" + right_txt
                    topic_match = re.search(r'Tema\s+(\d+[\.\s\-:]*[^:\n\.]+)', combined_page_txt)
                    if topic_match:
                        current_tema = topic_match.group(0).strip()

                    running_text_stream += "\n" + left_txt + "\n" + right_txt

                    steps_completed += 1
                    percentage = int((steps_completed / total_to_process) * 100)
                    self.progress_updated.emit(percentage)

                questions = parse_pdf_stream(running_text_stream, current_specialty, current_tema)
                questions = self._apply_intake_filters(questions)
                self.parsing_complete.emit(questions)

        except Exception as e:
            self.parsing_error.emit(str(e))
