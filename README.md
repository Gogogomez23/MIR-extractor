# Production MIR Extractor Engine Suite

An enterprise-grade Python application built using the PyQt6 desktop ecosystem framework. It delivers a fast, local, and reliable pipeline to convert raw PDF documents into structured clinical quiz formats.

## Key Core Architectures
* **Multithreaded Background Operations:** Parsing calculations are handled on a secondary worker thread (`QThread`) to ensure the graphical interface never enters a frozen state.
* **Relational Local Storage Database:** Persistent storage is powered by a local SQLite engine. It eliminates in-memory data drop crashes during long 100+ page processing jobs.
* **Regex Lookahead Boundary State Engine:** Automatically separates questions even when text layouts split awkwardly across columns or page boundaries.

## Installation and Execution Steps

1. Install required dependencies:
```bash
pip install PyQt6 pdfplumber