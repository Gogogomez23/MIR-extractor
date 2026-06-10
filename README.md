# Production MIR Extractor Engine Suite
v1.0.0

An enterprise-grade Python application built using the PyQt6 desktop ecosystem framework. It delivers a fast, local, and reliable pipeline to convert raw PDF documents into structured clinical quiz formats.

## Key Core Architectures
* **Multithreaded Background Operations:** Parsing calculations are handled on a secondary worker thread (`QThread`) to ensure the graphical interface never enters a frozen state.
* **Relational Local Storage Database:** Persistent storage is powered by a local SQLite engine with parent `extractions` batches, foreign-key linked questions, duplicate detection across prior batches, and a per-question revision flag.
* **Regex Lookahead Boundary State Engine:** Automatically separates questions even when text layouts split awkwardly across columns or page boundaries.
* **Revision Workbench Navigation:** The edit tab now supports batch filtering, saved-order previous/next navigation, a DB-backed quick selector, a revision toggle, and a dedicated question-number textbox without changing the exported document structure.

## Installation and Execution Steps

1. Install required dependencies:
```bash
pip install PyQt6 pdfplumber
