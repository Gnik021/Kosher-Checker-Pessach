# Pessach Medication Checker 2.0

A professional-grade automated system for analyzing medication suitability for the Passover holiday. Built with **Scrapy**, **Pydantic**, and **Playwright**.

## 🚀 Overview

This system automates the process of finding and analyzing medication ingredient lists from two primary sources:
1.  **BASG (Official Austrian Register)**: The primary source for official medication data.
2.  **Apotheken-Umschau**: A secondary fallback source for medications missing from the official register.

The system extracting ingredient sections from PDFs using advanced regex and categorizes them into four suitability levels based on a predefined keyword database.

## 🛠️ Technology Stack
- **Framework**: Scrapy (Spider-based concurrent crawling)
- **Validation**: Pydantic (Strict data models and type safety)
- **Automation**: Playwright (Smart Bearer token capture)
- **PDF Extraction**: PyMuPDF (High-precision text extraction)
- **Keyword Engine**: FlashText (Highly efficient keyword matching)

## 📁 Structure
- `med_crawler/`: Scrapy project and core logic.
  - `models.py`: Data models and Enums.
  - `logic.py`: Analysis engine and PDF extractor.
  - `spiders/`: Scrapy spiders for BASG and AU.
- `run_pessach_2.0.py`: Main entry point for the sequential pipeline.
- `Koscher_Medikamente_Pessach.csv`: Input medication list.

## 🏃 Usage

Ensure all dependencies are installed, then run the orchestrator:

```bash
python run_pessach_2.0.py
```

The system will:
1.  Capture the necessary authentication tokens.
2.  Search the BASG database for all medications.
3.  Identify missed items and search Apotheken-Umschau for fallbacks.
4.  Analyze all extracted ingredients.
5.  Generate a professional Excel report: `Pessach_Medikamente_2.0.xlsx`.

## 🛡️ Best Practices
- **Confidence Scores**: Every result includes a Confidence rating (HIGH/MEDIUM/LOW) so you can verify low-confidence extractions manually if needed.
- **Error Handling**: Robust process management and JSON-based intermediate storage ensure data integrity.
