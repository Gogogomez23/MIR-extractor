from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QProgressBar, QLabel
from core.database import get_all_questions
from ui.tabs.import_tab import ImportTab
from ui.tabs.edit_tab import EditTab
from ui.tabs.export_wizard_tab import ExportWizardTab
from ui.tabs.manage_db_tab import ManageDBTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Production MIR Extractor Engine Suite")
        self.setGeometry(100, 100, 1150, 800)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        master_layout = QVBoxLayout(central_widget)

        # Tab Router Navigation System Frame Matrix
        self.tabs = QTabWidget()
        self.import_tab = ImportTab(self)
        self.export_wizard_tab = ExportWizardTab(self)
        self.edit_tab = EditTab(self)
        self.manage_db_tab = ManageDBTab(self)

        self.tabs.addTab(self.import_tab, "Pipeline Engine (Import/Table)")
        self.tabs.addTab(self.export_wizard_tab, "Export Wizard")
        self.tabs.addTab(self.edit_tab, "Revision Workbench (Edit Form)")
        self.tabs.addTab(self.manage_db_tab, "DB Admin Console")
        master_layout.addWidget(self.tabs)

        # Cross-Tab Signals routing linkage map setup boundary parameters
        self.import_tab.question_selected_for_edit.connect(self.route_to_editor)
        self.manage_db_tab.database_mutated.connect(self.handle_database_mutation)
        self.manage_db_tab.batch_open_requested.connect(self.route_to_batch_editor)

        # System Pipeline Processing Progress Control Bars Footer
        self.lbl_progress = QLabel("System Status: Operational / Monitoring Local DB File System Storage")
        master_layout.addWidget(self.lbl_progress)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        master_layout.addWidget(self.progress_bar)

    def route_to_editor(self, question_data_dict):
        self.edit_tab.load_question_details(question_data_dict)
        self.tabs.setCurrentWidget(self.edit_tab)

    def route_to_batch_editor(self, batch_id):
        questions = get_all_questions(extraction_id=batch_id)
        if questions:
            self.edit_tab.load_question_details(questions[0])
        else:
            self.edit_tab.refresh_data_views(select_batch_id=batch_id)
        self.tabs.setCurrentWidget(self.edit_tab)

    def handle_database_mutation(self):
        self.import_tab.load_table_data()
        self.edit_tab.refresh_data_views()
        self.export_wizard_tab.refresh_data_sources()
        self.manage_db_tab.refresh_dashboard()
