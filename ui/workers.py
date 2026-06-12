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

    def _matches_year_filter(self, question_year_str, filter_text):
        if not filter_text:
            return True
        
        try:
            q_year = int(str(question_year_str).strip())
        except (ValueError, TypeError):
            return False

        filter_text = filter_text.strip()
        if "-" in filter_text:
            parts = filter_text.split("-")
            if len(parts) == 2:
                try:
                    start_year = int(parts[0].strip())
                    end_year = int(parts[1].strip())
                    return start_year <= q_year <= end_year
                except ValueError:
                    return False
        else:
            try:
                target_year = int(filter_text)
                return q_year == target_year
            except ValueError:
                return False
        return False

    def _matches_intake_filters(self, question, year_filter, ignore_images, page_has_images):
        if not self._matches_year_filter(question.get("ano", ""), year_filter):
            return False

        if ignore_images:
            if page_has_images:
                return False
            full_enunciado = question.get("enunciado", "").lower()
            if "imagen" in full_enunciado or "figura" in full_enunciado:
                return False

        return True

    def _apply_intake_filters(self, questions_with_metadata):
        year_filter = self.intake_filters.get("year")
        ignore_images = self.intake_filters.get("ignore_images", False)
        
        if not year_filter and not ignore_images:
            return [q for q, _ in questions_with_metadata]

        filtered_questions = []
        for question, page_has_images in questions_with_metadata:
            if self._matches_intake_filters(question, year_filter, ignore_images, page_has_images):
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

                all_parsed_questions = []
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

                    # Determine if page has visual elements
                    page_has_images = (len(page.images) > 0 or len(page.rects) > 0)
                    
                    page_questions = parse_pdf_stream(combined_page_txt, current_specialty, current_tema)
                    for q in page_questions:
                        all_parsed_questions.append((q, page_has_images))

                    steps_completed += 1
                    percentage = int((steps_completed / total_to_process) * 100)
                    self.progress_updated.emit(percentage)

                questions = self._apply_intake_filters(all_parsed_questions)
                self.parsing_complete.emit(questions)

        except Exception as e:
            self.parsing_error.emit(str(e))
