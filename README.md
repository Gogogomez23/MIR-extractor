# Production MIR Extractor Engine Suite
**Version:** 1.7.2

An enterprise-grade Python application built using the PyQt6 desktop ecosystem framework. It delivers a fast, local, and reliable pipeline to convert raw PDF documents into structured clinical quiz formats.

## Key Core Architectures
* **Multithreaded Background Operations:** Parsing calculations are handled on a secondary worker thread (`QThread`) to ensure the graphical interface never enters a frozen state.
* **Relational Local Storage Database:** Persistent storage is powered by a local SQLite engine with parent `extractions` batches, foreign-key linked questions, duplicate detection across prior batches, and a per-question revision flag.
* **Current Batch Import View:** The import tab now shows only the absolute latest extraction batch, split across `Año` and `Nº Pregunta`, with a quick export path scoped to that current batch.
* **Intake Validation Filters:** The import workflow supports full-document intake mode, year range filters (e.g., "2022" or "2018-2022"), image-exclusion filtering (ignoring questions with figures/images), and selectable duplicate handling policies before rows are committed to SQLite.
* **Database Explorer Master Log:** A dedicated read-only tab provides a filtered historical view of every stored question, with batch and revision filters plus direct routing back into the edit workbench.
* **Database Admin Console:** A dedicated tab manages extraction batches, batch exports, safe purges, destructive resets, and live database metrics from the same SQLite file.
* **Custom Export Wizard:** A separate export tab supports batch/year/specialty/revision filters, multiple ordering modes, and uses the exact same quick-export text template for filtered document generation, with an optional informational header.
* **Batch Export Formatting Consistency:** Batch exports from the DB admin console reuse the exact quick-export body and can optionally prepend the same style of export header.
* **Regex Lookahead Boundary State Engine:** Automatically separates questions even when text layouts split awkwardly across columns or page boundaries.
* **Revision Workbench Navigation:** The edit tab now supports batch filtering, saved-order previous/next navigation, a DB-backed quick selector, a revision toggle, a dedicated question-number textbox, and shared database refresh signaling without changing the exported document structure.

## Installation and Execution Steps

1. Install required dependencies:
```bash
pip install PyQt6 pdfplumber
