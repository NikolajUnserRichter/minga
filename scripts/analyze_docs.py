
import pandas as pd
from pypdf import PdfReader
import os

EXCEL_FILE = "Input/260128_Kunden-Adminprozess-Dokumente.xlsx"
PDF_FILE = "Input/MingaGreens_Adminprozess.drawio.pdf"

def analyze_excel():
    print(f"\n=== ANALYZING EXCEL: {EXCEL_FILE} ===")
    try:
        # Read all sheets
        xls = pd.ExcelFile(EXCEL_FILE)
        print(f"Sheets found: {xls.sheet_names}")
        
        for sheet_name in xls.sheet_names:
            print(f"\n--- Sheet: {sheet_name} ---")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            # Print columns
            print(f"Columns: {list(df.columns)}")
            # Print content (first 50 rows to capture most process steps)
            print(df.head(50).to_string())
            
    except Exception as e:
        print(f"Error reading Excel: {e}")

def analyze_pdf():
    print(f"\n=== ANALYZING PDF: {PDF_FILE} ===")
    try:
        reader = PdfReader(PDF_FILE)
        print(f"Number of pages: {len(reader.pages)}")
        
        for i, page in enumerate(reader.pages):
            print(f"\n--- Page {i+1} ---")
            text = page.extract_text()
            print(text)
            
    except Exception as e:
        print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    analyze_excel()
    analyze_pdf()
