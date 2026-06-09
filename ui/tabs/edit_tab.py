from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QTextEdit, QComboBox, QPushButton, QMessageBox)
from core.database import update_question


class EditTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_q_id = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Active Reference State Label header info tracking indicators
        self.lbl_active_ref = QLabel("Select a question from the grid to modify parameters...")
        self.lbl_active_ref.setStyleSheet("font-weight: bold; color: #3b82f6; font-size: 13px;")
        layout.addWidget(self.lbl_active_ref)

        # Enunciado Field Box
        layout.addWidget(QLabel("Enunciado:"))
        self.txt_enunciado = QTextEdit()
        self.txt_enunciado.setMaximumHeight(100)
        layout.addWidget(self.txt_enunciado)

        # Options input cluster grid structure matrix arrays
        self.opt_inputs = []
        for idx in range(1, 6):
            opt_lay = QHBoxLayout()
            opt_lay.addWidget(QLabel(f"Option {idx}:"))
            ledit = QLineEdit()
            opt_lay.addWidget(ledit)
            self.opt_inputs.append(ledit)
            layout.addLayout(opt_lay)

        # Metadata adjustment block rows
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

        # Commentary Analysis box
        layout.addWidget(QLabel("Explicación:"))
        self.txt_explicacion = QTextEdit()
        layout.addWidget(self.txt_explicacion)

        # Action Execution Buttons control clusters
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
        self.entry_rc.setEnabled(enabled)
        self.combo_diff.setEnabled(enabled)
        self.txt_explicacion.setEnabled(enabled)
        self.btn_ai_mock.setEnabled(enabled)
        self.btn_save_changes.setEnabled(enabled)
        for ledit in self.opt_inputs:
            ledit.setEnabled(enabled)

    def load_question_details(self, question_dict):
        self.current_q_id = question_dict["id"]
        self.toggle_form_state(True)

        self.lbl_active_ref.setText(
            f"Modifying Active Object: MIR {question_dict['ano']} - Question {question_dict['num']}")
        self.txt_enunciado.setPlainText(question_dict["enunciado"])
        self.entry_rc.setText(question_dict["rc"])

        # Safe string dropdown matching loop boundary parameters
        index = self.combo_diff.findText(question_dict["dificultad"])
        if index >= 0:
            self.combo_diff.setCurrentIndex(index)

        self.txt_explicacion.setPlainText(question_dict["explicacion"])

        # Populate arrays cleanly tracking string positions length boundaries
        for i, ledit in enumerate(self.opt_inputs):
            if i < len(question_dict["opciones"]):
                ledit.setText(question_dict["opciones"][i])
            else:
                ledit.clear()

    def trigger_ai_mockup(self):
        # AI Summarization mockup tracking logic sequence layer parameters
        current_text = self.txt_explicacion.toPlainText().strip()
        if not current_text:
            QMessageBox.warning(self, "AI Notice",
                                "No text found inside explanation field to execute summary transformation on.")
            return

        mocked_summary = f"[AI Summary Applied]: The text was parsed through Gemini 1.5 Flash. Primary points are: {current_text[:120]}..."
        self.txt_explicacion.setPlainText(mocked_summary)
        QMessageBox.information(self, "API Mock Response",
                                "Gemini AI Agent simulated pipeline ran successfully. Summary values assigned.")

    def commit_form_updates(self):
        if not self.current_q_id:
            return

        opts = [ledit.text().strip() for ledit in self.opt_inputs if ledit.text().strip() != ""]

        # Re-evaluate validation status tags cleanly dynamically on saving tracking updates
        rc_val = self.entry_rc.text().strip()
        exp_val = self.txt_explicacion.toPlainText().strip()

        status = "🟢 OK"
        msg = "Correctly parsed."
        if rc_val == "Unknown" or not exp_val:
            status = "🟡 REVIEW"
            msg = "Missing explanation text or Answer index."
        if len(opts) < 4:
            status = "🔴 ERROR"
            msg = "Options structure is corrupted."

        updated_payload = {
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
            QMessageBox.information(self, "Success",
                                    "Question record modifications committed successfully to local SQLite file store.")

            # Refresh presentation tables back on initial navigation panel
            self.main_window.tabs.setCurrentIndex(0)
            self.main_window.import_tab.load_table_data()
        except Exception as e:
            QMessageBox.critical(self, "Write Error", f"Could not update question record database entry: {str(e)}")