import os
import re
import pandas as pd
import sys
from typing import List, Dict, Any

# Add current dir to path for local imports
sys.path.append(os.getcwd())
from med_crawler.logic import PessachAnalyzer, extract_from_pdf
from med_crawler.utils import normalize_med_name

# Configuration
PROJECT_DIR = os.getcwd()
PDF_DIR = os.path.join(PROJECT_DIR, "temp_pdfs")
ORIGINAL_CSV = os.path.join(PROJECT_DIR, "Koscher_Medikamente_Pessach.csv")
EXISTING_XLSX_1 = os.path.join(PROJECT_DIR, "Pessach_Medikamente_AT_Final.xlsx")
EXISTING_XLSX_2 = os.path.join(PROJECT_DIR, "Pessach_Medikamente_2.0.xlsx")
OUTPUT_XLSX = os.path.join(PROJECT_DIR, "Pessach_Medikamente_Premium_Final.xlsx")

def clean_med_name(name: str) -> str:
    """Removes all technical tags and extra spaces."""
    name = str(name)
    name = re.sub(r"\[.*?\]", "", name)  # Remove [NEU], [AU], etc.
    name = re.sub(r"\(.*?\)", "", name)  # Remove (Warnung: ...)
    return name.strip()

def main():
    print("🚀 Starting Premium Polishing & Deduplication...")
    
    analyzer = PessachAnalyzer()
    
    # 1. Load Original List to distinguish "NEW"
    original_meds = set()
    if os.path.exists(ORIGINAL_CSV):
        df_orig = pd.read_csv(ORIGINAL_CSV, sep=';')
        original_meds = {clean_med_name(m).lower() for m in df_orig['Medikament'].dropna()}
    
    # 2. Collect all unique medications from existing results
    all_results = {} # key: cleaned name lower, value: dict of best result data
    
    def process_df(df):
        for _, row in df.iterrows():
            prod_raw = row.get('Produkt', '')
            clean_name = clean_med_name(prod_raw)
            key = clean_name.lower()
            
            # If we don't have this or if existing one is a "not found" entry, replace it
            current_status = str(row.get('Grund für Einstufung', '')).lower()
            is_new_found = 'nicht gefunden' not in current_status
            
            existing = all_results.get(key)
            if not existing or (is_new_found and 'nicht gefunden' in str(existing.get('Grund für Einstufung', '')).lower()):
                all_results[key] = row.to_dict()
                all_results[key]['Produkt'] = clean_name # Store cleaned version

    if os.path.exists(EXISTING_XLSX_1):
        process_df(pd.read_excel(EXISTING_XLSX_1))
    if os.path.exists(EXISTING_XLSX_2):
        process_df(pd.read_excel(EXISTING_XLSX_2))

    print(f"📦 Collected {len(all_results)} unique medications from existing reports.")

    # 3. Re-Verify all PDFs in temp_pdfs and Update Results
    print(f"📂 Re-verifying {len(os.listdir(PDF_DIR))} PDFs in temp_pdfs...")
    
    # Map PDFs to all_results
    # BASG PDFs are often numbers (authNumber), AU PDFs are AU_name.pdf
    for pdf_file in os.listdir(PDF_DIR):
        if not pdf_file.endswith(".pdf"): continue
        
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        
        # Try to find which medication this PDF belongs to
        target_med_key = None
        
        # Attempt 1: Match with AU prefix
        if pdf_file.startswith("AU_"):
            # AU_Adolorin_Ibuforte.pdf -> adolorin ibuforte
            med_part = pdf_file[3:-4].replace("_", " ").lower()
            # This is a bit fuzzy, let's see if any key contains this
            for key in all_results:
                if med_part in key:
                    target_med_key = key
                    break
        
        # Attempt 2: If we have the source URL in results, match it
        if not target_med_key:
            for key, data in all_results.items():
                source = str(data.get('Quelle', ''))
                if pdf_file in source:
                    target_med_key = key
                    break
        
        # If we found a match, re-analyze
        if target_med_key:
            try:
                ing_data = extract_from_pdf(pdf_path)
                analysis = analyzer.analyze(all_results[target_med_key]['Produkt'], ing_data)
                
                # Update record
                all_results[target_med_key].update({
                    'Kategorie': analysis.category.value,
                    'Grund für Einstufung': analysis.reason,
                    'Gefundene Problematische Stoffe': ", ".join(analysis.problematic_substances) if analysis.problematic_substances else "",
                    'Hilfsstoffe': analysis.raw_ingredients,
                    'Quelle': pdf_path # Use local path for final confirmation or keep it as is
                })
            except Exception as e:
                print(f"⚠️ Error re-verifying {pdf_file}: {e}")

    # 4. Final Cleanup and Tagging
    final_data = []
    for key, data in all_results.items():
        name = data['Produkt']
        
        # Add [NEU] tag if not in original list
        if key not in original_meds:
            name = f"[NEU] {name}"
            
        data['Produkt'] = name
        
        # Ensure consistent column ordering
        final_data.append({
            'Produkt': data.get('Produkt'),
            'Kategorie': data.get('Kategorie'),
            'Grund für Einstufung': data.get('Grund für Einstufung'),
            'Gefundene Problematische Stoffe': data.get('Gefundene Problematische Stoffe'),
            'Warnung Darreichungsform': data.get('Warnung Darreichungsform', 'Nein'),
            'Hilfsstoffe': data.get('Hilfsstoffe'),
            'Quelle': data.get('Quelle')
        })

    # 5. Export with Premium Formatting
    df_final = pd.DataFrame(final_data)
    
    # Sort: Category Priority (Nicht koscher -> Nicht für Pessach -> Verdacht Chometz -> OK)
    cat_order = {"Nicht koscher": 0, "Nicht für Pessach": 1, "Verdacht Chometz": 2, "OK": 3}
    df_final['cat_sort'] = df_final['Kategorie'].map(cat_order).fillna(4)
    df_final = df_final.sort_values(['cat_sort', 'Produkt']).drop(columns=['cat_sort'])

    print(f"📊 Generating Premium Excel: {OUTPUT_XLSX}")
    
    with pd.ExcelWriter(OUTPUT_XLSX, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Analyseergebnisse')
        
        workbook = writer.book
        worksheet = writer.sheets['Analyseergebnisse']
        
        # Formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        ok_format = workbook.add_format({'bg_color': '#D9EAD3', 'font_color': '#274E13'}) # Green
        nfp_format = workbook.add_format({'bg_color': '#F4CCCC', 'font_color': '#660000'}) # Red
        vc_format = workbook.add_format({'bg_color': '#FFF2CC', 'font_color': '#7F6000'}) # Yellow/Orange
        nk_format = workbook.add_format({'bg_color': '#EAD1DC', 'font_color': '#4C1130'}) # Purple/Dark Red
        
        # Apply header format
        for col_num, value in enumerate(df_final.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # Freeze panes
        worksheet.freeze_panes(1, 1)
        
        # Set column widths
        worksheet.set_column('A:A', 40) # Produkt
        worksheet.set_column('B:B', 20) # Kategorie
        worksheet.set_column('C:C', 50) # Grund
        worksheet.set_column('D:D', 30) # Probleme
        worksheet.set_column('E:E', 15) # Warnung
        worksheet.set_column('F:F', 100) # Hilfsstoffe
        worksheet.set_column('G:G', 50) # Quelle
        
        # Apply conditional formatting based on Kategorie
        row_count = len(df_final)
        worksheet.conditional_format(1, 0, row_count, 6, {
            'type': 'formula',
            'criteria': '=$B2="OK"',
            'format': ok_format
        })
        worksheet.conditional_format(1, 0, row_count, 6, {
            'type': 'formula',
            'criteria': '=$B2="Nicht für Pessach"',
            'format': nfp_format
        })
        worksheet.conditional_format(1, 0, row_count, 6, {
            'type': 'formula',
            'criteria': '=$B2="Verdacht Chometz"',
            'format': vc_format
        })
        worksheet.conditional_format(1, 0, row_count, 6, {
            'type': 'formula',
            'criteria': '=$B2="Nicht koscher"',
            'format': nk_format
        })
        
        # Add Autofilters
        worksheet.autofilter(0, 0, row_count, 6)
        
        # Add Summary Sheet
        summary_df = pd.DataFrame({
            'Kategorie': df_final['Kategorie'].value_counts().index,
            'Anzahl': df_final['Kategorie'].value_counts().values
        })
        summary_df.to_excel(writer, index=False, sheet_name='Zusammenfassung')
        
    print("✅ Polishing Complete! Final report is ready.")

if __name__ == "__main__":
    main()
