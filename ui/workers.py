from PyQt6.QtCore import QThread, pyqtSignal
import pdfplumber
import re
from core.parser import clean_text_hyphens, parse_pdf_stream


class PDFParseWorker(QThread):
    progress_updated = pyqtSignal(int)
    parsing_complete = pyqtSignal(list)
    parsing_error = pyqtSignal(str)

    def __init__(self, pdf_path, start_page, end_page):
        super().__init__()
        self.pdf_path = pdf_path
        self.start_page = start_page
        self.end_page = end_page

    def run(self):
        try:
            extracted_batch = []
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
                self.parsing_complete.emit(questions)

        except Exception as e:
            self.parsing_error.emit(str(e))