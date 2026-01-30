import pandas as pd
from pypdf import PdfReader
import os

pdf_path = '/Users/nikolajunser-richter/minga-greens-erp/Input/MingaGreens_Adminprozess.drawio.pdf'
excel_path = '/Users/nikolajunser-richter/minga-greens-erp/Input/260128_Kunden-Adminprozess-Dokumente.xlsx'

def extract_pdf(path):
    print(f"\n=== PROCESSING PDF: {os.path.basename(path)} ===\n")
    try:
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages):
            print(f"--- Page {i+1} ---")
            print(page.extract_text())
            print("\n")
    except Exception as e:
        print(f"Error reading PDF: {e}")

def extract_excel(path):
    print(f"\n=== PROCESSING EXCEL: {os.path.basename(path)} ===\n")
    try:
        xls = pd.ExcelFile(path)
        for sheet_name in xls.sheet_names:
            print(f"--- Sheet: {sheet_name} ---")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            print(df.to_string())
            print("\n")
    except Exception as e:
        print(f"Error reading Excel: {e}")

if __name__ == "__main__":
    if os.path.exists(pdf_path):
        extract_pdf(pdf_path)
    else:
        print(f"PDF not found at {pdf_path}")

    if os.path.exists(excel_path):
        extract_excel(excel_path)
    else:
        print(f"Excel not found at {excel_path}")
