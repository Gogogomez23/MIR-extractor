from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QComboBox, QPushButton, QMessageBox
)
from core.database import get_all_questions, update_question


class EditTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_q_id = None
        self.current_question_data = None
        self.question_order = []
        self.question_index_by_id = {}
        self.init_ui()
        self.refresh_question_list()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_active_ref = QLabel(
            "Select a question from the grid or dropdown to modify parameters..."
        )
        self.lbl_active_ref.setStyleSheet("font-weight: bold; color: #3b82f6; font-size: 13px;")
        layout.addWidget(self.lbl_active_ref)

        nav_row = QHBoxLayout()

        self.btn_prev_question = QPushButton("Previous Question")
        self.btn_prev_question.clicked.connect(lambda: self.go_to_adjacent_question(-1))
        nav_row.addWidget(self.btn_prev_question)

        self.btn_next_question = QPushButton("Next Question")
        self.btn_next_question.clicked.connect(lambda: self.go_to_adjacent_question(1))
        nav_row.addWidget(self.btn_next_question)

        nav_row.addWidget(QLabel("Jump to DB Question:"))
        self.combo_question_selector = QComboBox()
        self.combo_question_selector.currentIndexChanged.connect(self.handle_question_selection_from_dropdown)
        nav_row.addWidget(self.combo_question_selector, 1)
        layout.addLayout(nav_row)

        layout.addWidget(QLabel("Question Number:"))
        self.entry_question_num = QLineEdit()
        self.entry_question_num.setPlaceholderText("Question number")
        self.entry_question_num.setMaximumWidth(120)
        layout.addWidget(self.entry_question_num)

        layout.addWidget(QLabel("Enunciado:"))
        self.txt_enunciado = QTextEdit()
        self.txt_enunciado.setMaximumHeight(100)
        layout.addWidget(self.txt_enunciado)

        self.opt_inputs = []
        for idx in range(1, 6):
            opt_lay = QHBoxLayout()
            opt_lay.addWidget(QLabel(f"Option {idx}:"))
            ledit = QLineEdit()
            opt_lay.addWidget(ledit)
            self.opt_inputs.append(ledit)
            layout.addLayout(opt_lay)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("RC Index Number:"))
        self.entry_rc = QLineEdit()
        self.entry_rc.setFixedWidth(40)
        meta_row.addWidget(self.entry_rc)

        meta_row.addWidget(QLabel("Difficulty Status Dropdown:"))
        self.combo_diff = QComboBox()
        self.combo_diff.addItems(["Fácil", "Media", "Difícil"])
        meta_row.addWidget(self.combo_diff)

        meta_row.addStretch()
        layout.addLayout(meta_row)

        layout.addWidget(QLabel("Explicación:"))
        self.txt_explicacion = QTextEdit()
        layout.addWidget(self.txt_explicacion)

        btn_layout = QHBoxLayout()
        self.btn_ai_mock = QPushButton("✨ Summarize Explanation with AI")
        self.btn_ai_mock.clicked.connect(self.trigger_ai_mockup)
        btn_layout.addWidget(self.btn_ai_mock)

        self.btn_save_changes = QPushButton("Save Structural Edits")
        self.btn_save_changes.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self.btn_save_changes.clicked.connect(self.commit_form_updates)
        btn_layout.addWidget(self.btn_save_changes)
        layout.addLayout(btn_layout)

        self.toggle_form_state(False)

    def toggle_form_state(self, enabled=True):
        self.txt_enunciado.setEnabled(enabled)
        self.entry_question_num.setEnabled(enabled)
        self.entry_rc.setEnabled(enabled)
        self.combo_diff.setEnabled(enabled)
        self.txt_explicacion.setEnabled(enabled)
        self.btn_ai_mock.setEnabled(enabled)
        self.btn_save_changes.setEnabled(enabled)
        self.btn_prev_question.setEnabled(enabled and self.has_previous_question())
        self.btn_next_question.setEnabled(enabled and self.has_next_question())
        for ledit in self.opt_inputs:
            ledit.setEnabled(enabled)

    def clear_form_fields(self):
        self.entry_question_num.clear()
        self.txt_enunciado.clear()
        for ledit in self.opt_inputs:
            ledit.clear()
        self.entry_rc.clear()
        self.combo_diff.setCurrentIndex(1)
        self.txt_explicacion.clear()

    def update_active_ref_label(self):
        if not self.current_question_data:
            self.lbl_active_ref.setText(
                "Select a question from the grid or dropdown to modify parameters..."
            )
            return

        year = self.current_question_data.get("ano", "----")
        question_num = self.entry_question_num.text().strip() or self.current_question_data.get("num", "")
        self.lbl_active_ref.setText(
            f"Modifying Active Object: MIR {year} - Question {question_num}"
        )

    def refresh_question_list(self, select_q_id=None):
        self.question_order = get_all_questions()
        self.question_index_by_id = {}

        self.combo_question_selector.blockSignals(True)
        try:
            self.combo_question_selector.clear()
            self.combo_question_selector.setPlaceholderText("Select a question from the database...")

            if not self.question_order:
                self.combo_question_selector.setEnabled(False)
                self.combo_question_selector.setCurrentIndex(-1)
                self.current_q_id = None
                self.current_question_data = None
                self.clear_form_fields()
                self.update_active_ref_label()
                self.toggle_form_state(False)
                return

            for idx, question in enumerate(self.question_order):
                label = f"MIR {question['ano']} - Q{question['num']} [{question['status']}]"
                self.combo_question_selector.addItem(label, question["id"])
                self.question_index_by_id[question["id"]] = idx

            self.combo_question_selector.setEnabled(True)
            target_id = select_q_id if select_q_id is not None else self.current_q_id
            if target_id in self.question_index_by_id:
                self.combo_question_selector.setCurrentIndex(self.question_index_by_id[target_id])
            else:
                self.combo_question_selector.setCurrentIndex(-1)
        finally:
            self.combo_question_selector.blockSignals(False)

        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        if not self.current_q_id or self.current_q_id not in self.question_index_by_id:
            self.btn_prev_question.setEnabled(False)
            self.btn_next_question.setEnabled(False)
            return

        current_index = self.question_index_by_id[self.current_q_id]
        self.btn_prev_question.setEnabled(current_index > 0)
        self.btn_next_question.setEnabled(current_index < len(self.question_order) - 1)

    def has_previous_question(self):
        if not self.current_q_id or self.current_q_id not in self.question_index_by_id:
            return False
        return self.question_index_by_id[self.current_q_id] > 0

    def has_next_question(self):
        if not self.current_q_id or self.current_q_id not in self.question_index_by_id:
            return False
        return self.question_index_by_id[self.current_q_id] < len(self.question_order) - 1

    def load_question_details(self, question_dict):
        self.refresh_question_list(select_q_id=question_dict["id"])
        self.current_q_id = question_dict["id"]
        self.current_question_data = dict(question_dict)

        self.toggle_form_state(True)
        self.entry_question_num.setText(question_dict["num"])

        self.update_active_ref_label()
        self.txt_enunciado.setPlainText(question_dict["enunciado"])
        self.entry_rc.setText(question_dict["rc"])

        index = self.combo_diff.findText(question_dict["dificultad"])
        if index >= 0:
            self.combo_diff.setCurrentIndex(index)

        self.txt_explicacion.setPlainText(question_dict["explicacion"])

        for i, ledit in enumerate(self.opt_inputs):
            if i < len(question_dict["opciones"]):
                ledit.setText(question_dict["opciones"][i])
            else:
                ledit.clear()

        self.update_navigation_buttons()

    def handle_question_selection_from_dropdown(self, index):
        if index < 0:
            return

        selected_q_id = self.combo_question_selector.itemData(index)
        if selected_q_id is None:
            return

        target_q = next((q for q in self.question_order if q["id"] == selected_q_id), None)
        if target_q:
            self.load_question_details(target_q)

    def go_to_adjacent_question(self, step):
        if not self.current_q_id or self.current_q_id not in self.question_index_by_id:
            return

        current_index = self.question_index_by_id[self.current_q_id]
        target_index = current_index + step
        if target_index < 0 or target_index >= len(self.question_order):
            QMessageBox.information(
                self,
                "Navigation Notice",
                "You are already at the edge of the saved question order."
            )
            return

        self.load_question_details(self.question_order[target_index])

    def trigger_ai_mockup(self):
        current_text = self.txt_explicacion.toPlainText().strip()
        if not current_text:
            QMessageBox.warning(
                self,
                "AI Notice",
                "No text found inside explanation field to execute summary transformation on."
            )
            return

        mocked_summary = (
            f"[AI Summary Applied]: The text was parsed through Gemini 1.5 Flash. "
            f"Primary points are: {current_text[:120]}..."
        )
        self.txt_explicacion.setPlainText(mocked_summary)
        QMessageBox.information(
            self,
            "API Mock Response",
            "Gemini AI Agent simulated pipeline ran successfully. Summary values assigned."
        )

    def commit_form_updates(self):
        if not self.current_q_id:
            return

        opts = [ledit.text().strip() for ledit in self.opt_inputs if ledit.text().strip() != ""]
        rc_val = self.entry_rc.text().strip()
        exp_val = self.txt_explicacion.toPlainText().strip()
        question_num = self.entry_question_num.text().strip()

        if not question_num:
            QMessageBox.warning(
                self,
                "Validation Notice",
                "Question number cannot be empty."
            )
            return

        status = "🟢 OK"
        msg = "Correctly parsed."
        if rc_val == "Unknown" or not exp_val:
            status = "🟡 REVIEW"
            msg = "Missing explanation text or Answer index."
        if len(opts) < 4:
            status = "🔴 ERROR"
            msg = "Options structure is corrupted."

        updated_payload = {
            "num": question_num,
            "enunciado": self.txt_enunciado.toPlainText().strip(),
            "opciones": opts,
            "rc": rc_val,
            "tema": "Tema Identificado",
            "especialidad": "Especialidad Identificada",
            "dificultad": self.combo_diff.currentText(),
            "explicacion": exp_val,
            "status": status,
            "status_msg": msg
        }

        try:
            update_question(self.current_q_id, updated_payload)
            QMessageBox.information(
                self,
                "Success",
                "Question record modifications committed successfully to local SQLite file store."
            )

            self.refresh_question_list(select_q_id=self.current_q_id)
            self.update_active_ref_label()
            self.main_window.import_tab.load_table_data()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Write Error",
                f"Could not update question record database entry: {str(e)}"
            )
