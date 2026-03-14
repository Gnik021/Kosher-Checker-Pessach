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
OUTPUT_XLSX = os.path.join(PROJECT_DIR, "Pessach_Medikamente_Premium_Final_v2.xlsx")

def clean_med_name(name: str) -> str:
    """Removes all technical tags and extra spaces."""
    name = str(name)
    name = re.sub(r"\[.*?\]", "", name)  # Remove [NEU], [AU], etc.
    name = re.sub(r"\(.*?\)", "", name)  # Remove (Warnung: ...)
    return name.strip()

def main():
    print("🚀 Starting Premium Polishing & Deduplication...")
    
    analyzer = PessachAnalyzer()
    
    # 1. Load Original List
    orig_meds_list = []
    if os.path.exists(ORIGINAL_CSV):
        df_orig = pd.read_csv(ORIGINAL_CSV, sep=';')
        orig_meds_list = [str(m).strip() for m in df_orig['Medikament'].dropna()]
    
    # Normalized set of original names for fast lookup
    original_bases = {normalize_med_name(m)[0]: m for m in orig_meds_list if normalize_med_name(m)}
    
    # 2. Collect and Deduplicate Existing Results
    # Key: Base Name (from normalize_med_name), Value: Best Result Dict
    processed_by_base = {}
    
    def process_df(df):
        for _, row in df.iterrows():
            prod_raw = row.get('Produkt', '')
            clean_name = clean_med_name(prod_raw)
            variants = normalize_med_name(clean_name)
            if not variants: continue
            
            base = variants[0]
            
            # Merit system: Found > Not Found; Longer Name > Shorter Name if same status
            status = str(row.get('Grund für Einstufung', '')).lower()
            is_found = 'nicht gefunden' not in status
            
            existing = processed_by_base.get(base)
            if not existing:
                processed_by_base[base] = row.to_dict()
                processed_by_base[base]['Produkt'] = clean_name
            else:
                ext_status = str(existing.get('Grund für Einstufung', '')).lower()
                ext_found = 'nicht gefunden' not in ext_status
                
                # Update if new is found and old wasn't, or if same status but new name is longer/more specific
                if (is_found and not ext_found) or (is_found == ext_found and len(clean_name) > len(existing['Produkt'])):
                    processed_by_base[base] = row.to_dict()
                    processed_by_base[base]['Produkt'] = clean_name

    if os.path.exists(EXISTING_XLSX_1):
        process_df(pd.read_excel(EXISTING_XLSX_1))
    if os.path.exists(EXISTING_XLSX_2):
        process_df(pd.read_excel(EXISTING_XLSX_2))

    # 3. Re-Verify PDFs (Same logic as before, but updating processed_by_base)
    print(f"📂 Re-verifying {len(os.listdir(PDF_DIR))} PDFs...")
    for pdf_file in os.listdir(PDF_DIR):
        if not pdf_file.endswith(".pdf"): continue
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        
        target_base = None
        # Match by filename hint or source URL
        if pdf_file.startswith("AU_"):
            hint = pdf_file[3:-4].replace("_", " ").lower()
            for base in processed_by_base:
                if hint in base or base in hint:
                    target_base = base
                    break
        
        if not target_base:
            for base, data in processed_by_base.items():
                if pdf_file in str(data.get('Quelle', '')):
                    target_base = base
                    break
                    
        if target_base:
            try:
                ing_data = extract_from_pdf(pdf_path)
                analysis = analyzer.analyze(processed_by_base[target_base]['Produkt'], ing_data)
                processed_by_base[target_base].update({
                    'Kategorie': analysis.category.value,
                    'Grund für Einstufung': analysis.reason,
                    'Gefundene Problematische Stoffe': ", ".join(analysis.problematic_substances) if analysis.problematic_substances else "",
                    'Hilfsstoffe': analysis.raw_ingredients,
                    'Quelle': pdf_path
                })
            except Exception as e:
                pass

    # 4. Final Result Prep & [NEU] Tagging
    final_processed = []
    success_bases = set()
    
    for base, data in processed_by_base.items():
        name = data['Produkt']
        status = str(data.get('Grund für Einstufung', '')).lower()
        if 'nicht gefunden' in status: continue
        
        # Tagging: If base not in original bases, it's [NEU]
        if base not in original_bases:
            name = f"[NEU] {name}"
            
        data['Produkt'] = name
        final_processed.append(data)
        success_bases.add(base)

    # 5. Gap Analysis: Which originals are missing?
    missing_meds = []
    for orig_name in orig_meds_list:
        base = normalize_med_name(orig_name)[0]
        if base not in success_bases:
            missing_meds.append(orig_name)
    
    # Deduplicate missing list
    missing_meds = sorted(list(set(missing_meds)))

    # 6. Premium Export
    df_results = pd.DataFrame(final_processed)
    # Ensure columns
    cols = ['Produkt', 'Kategorie', 'Grund für Einstufung', 'Gefundene Problematische Stoffe', 'Warnung Darreichungsform', 'Hilfsstoffe', 'Quelle']
    df_results = df_results[[c for c in cols if c in df_results.columns]]
    
    cat_order = {"Nicht koscher": 0, "Nicht für Pessach": 1, "Verdacht Chometz": 2, "OK": 3}
    df_results['cat_sort'] = df_results['Kategorie'].map(cat_order).fillna(4)
    df_results = df_results.sort_values(['cat_sort', 'Produkt']).drop(columns=['cat_sort'])

    print(f"📊 Generating Premium Excel with {len(missing_meds)} missing items...")
    
    with pd.ExcelWriter(OUTPUT_XLSX, engine='xlsxwriter') as writer:
        df_results.to_excel(writer, index=False, sheet_name='Analyseergebnisse')
        
        # Missing Meds Sheet
        df_missing = pd.DataFrame({'Produkt (Fehlt)': missing_meds})
        df_missing.to_excel(writer, index=False, sheet_name='Fehlt')
        
        workbook = writer.book
        res_sheet = writer.sheets['Analyseergebnisse']
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        ok_format = workbook.add_format({'bg_color': '#D9EAD3', 'font_color': '#274E13'})
        nfp_format = workbook.add_format({'bg_color': '#F4CCCC', 'font_color': '#660000'})
        vc_format = workbook.add_format({'bg_color': '#FFF2CC', 'font_color': '#7F6000'})
        nk_format = workbook.add_format({'bg_color': '#EAD1DC', 'font_color': '#4C1130'})
        
        for col_num, value in enumerate(df_results.columns.values):
            res_sheet.write(0, col_num, value, header_format)
        res_sheet.freeze_panes(1, 1)
        res_sheet.set_column('A:A', 40); res_sheet.set_column('B:B', 20); res_sheet.set_column('C:C', 50)
        res_sheet.set_column('D:D', 30); res_sheet.set_column('E:E', 15); res_sheet.set_column('F:F', 100); res_sheet.set_column('G:G', 50)
        
        row_count = len(df_results)
        res_sheet.conditional_format(1, 0, row_count, 6, {'type': 'formula', 'criteria': '=$B2="OK"', 'format': ok_format})
        res_sheet.conditional_format(1, 0, row_count, 6, {'type': 'formula', 'criteria': '=$B2="Nicht für Pessach"', 'format': nfp_format})
        res_sheet.conditional_format(1, 0, row_count, 6, {'type': 'formula', 'criteria': '=$B2="Verdacht Chometz"', 'format': vc_format})
        res_sheet.conditional_format(1, 0, row_count, 6, {'type': 'formula', 'criteria': '=$B2="Nicht koscher"', 'format': nk_format})
        res_sheet.autofilter(0, 0, row_count, 6)
        
        # Format Missing sheet
        miss_sheet = writer.sheets['Fehlt']
        miss_sheet.set_column('A:A', 50)
        miss_sheet.write(0, 0, 'Produkt (Fehlt)', header_format)
        
        # Summary Sheet
        summary_df = pd.DataFrame({
            'Kategorie': df_results['Kategorie'].value_counts().index,
            'Anzahl': df_results['Kategorie'].value_counts().values
        })
        summary_df.loc[len(summary_df)] = ['FEHLEND (Nicht gefunden)', len(missing_meds)]
        summary_df.to_excel(writer, index=False, sheet_name='Zusammenfassung')
        
    print(f"✅ Polishing Complete! Total Processed: {len(df_results)}, Total Missing: {len(missing_meds)}")

if __name__ == "__main__":
    main()
