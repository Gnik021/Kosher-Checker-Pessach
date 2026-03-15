import os
import re
import pandas as pd
import sys
import fitz  # PyMuPDF
from typing import List, Dict, Any, Set

# Add current dir to path for local imports
sys.path.append(os.getcwd())
try:
    from med_crawler.logic import PessachAnalyzer, extract_from_pdf
    from med_crawler.utils import normalize_med_name
except ImportError:
    pass

# Configuration
PROJECT_DIR = os.getcwd()
PDF_DIR = os.path.join(PROJECT_DIR, "temp_pdfs")
ORIGINAL_CSV = os.path.join(PROJECT_DIR, "MEDIKAMENTE.csv")
MAPPING_CSV = os.path.join(PROJECT_DIR, "MAPPING LINKS.csv") # New Mapping File

RESULT_FILES = [
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_AT_Final.xlsx"),
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_2.0.xlsx"),
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_Premium_Final_v3.xlsx"),
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_POLISHED_V5.xlsx"),
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_FINAL_V6_AUDITED.xlsx"),
    os.path.join(PROJECT_DIR, "Pessach_Medikamente_MASTER_EDITION.xlsx")
]
# Final Audited Output
OUTPUT_XLSX = os.path.join(PROJECT_DIR, "Koscher_Medikamente_Pessach_FINAL_AUDIT.xlsx")

def stem_word(w):
    w = w.lower().strip()
    if len(w) <= 3: return w
    for end in ['es', 'en', 'e', 's', 'n']:
        if w.endswith(end):
            return w[:-len(end)]
    return w

def get_word_stems(name):
    if not name or str(name) == 'nan': return set()
    n = re.sub(r"\[.*?\]|\(.*?\)", "", str(name))
    n = re.sub(r"[^a-zA-Z0-9]", " ", n).lower()
    words = n.split()
    return {stem_word(w) for w in words if len(w) > 1}

def get_name_from_pdf(pdf_path: str) -> str:
    """Robust extraction of medication name from PDF."""
    try:
        doc = fitz.open(pdf_path)
        
        # Strategy 1: PDF Metadata Title
        meta_title = doc.metadata.get('title')
        if meta_title and len(meta_title) > 3 and not re.match(r"^\d+-\d+$", meta_title):
            # Check if it's not a generic boilerplate title
            if not any(b in meta_title.upper() for b in ["GEBRAUCHSINFORMATION", "GEBR_INFO", "FACHINFORMATION"]):
                return meta_title
        
        # Strategy 2: Section 1 Header Search
        first_pages = "".join([doc[i].get_text() for i in range(min(2, len(doc)))])
        lines = [l.strip() for l in first_pages.split('\n') if l.strip()]
        
        # Look for "1. BEZEICHNUNG DES ARZNEIMITTELS" followed by the name
        for i, line in enumerate(lines):
            line_up = line.upper()
            if "1. BEZEICHNUNG DES ARZNEIMITTELS" in line_up:
                # The next non-empty line is often the name
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = lines[j]
                    if len(candidate) > 3 and not re.match(r"^\d", candidate):
                        return candidate
        
        # Strategy 3: Heuristic boilerplate skip (existing logic improved)
        boilerplate = [
            "GEBRAUCHSINFORMATION", "FACHINFORMATION", "INFORMATION", "BASG",
            "PACKUNGSBEILAGE", "ANWENDER", "GEBRAUCHSANWEISUNG", "ZUSAMMENFASSUNG",
            "MERKMALE", "TEXT", "ÖSTERREICHISCHES", "ARZNEIMITTELREGISTER"
        ]
        
        for line in lines:
            line_up = line.upper()
            if len(line) < 3: continue
            if any(b == line_up or b + ":" == line_up for b in boilerplate): continue
            if "GEBRAUCHSINFORMATION" in line_up or "PACKUNGSBEILAGE" in line_up: continue
            if re.search(r'[a-zA-Z]', line) and not re.match(r"^\d+$", line):
                # Ensure it doesn't look like a filename or file number
                if not re.search(r"\.pdf$|\.doc$|\d+-\d+", line):
                    return line
        
        return "Name manuell prüfen" # Absolute fallback as requested
    except:
        return "Name manuell prüfen"

def main():
    print("💎 Starting Precision Polishing V10 (Mapping & Robust Naming)...")
    analyzer = PessachAnalyzer()
    
    # 1. Load MAPPING LINKS.csv (Semicolon delimited)
    url_mapping = {} # Name stems -> URL
    if os.path.exists(MAPPING_CSV):
        try:
            df_map = pd.read_csv(MAPPING_CSV, sep=';')
            for _, row in df_map.iterrows():
                med = str(row.get('Medikament', '')).strip()
                link = str(row.get('Link', '')).strip()
                if med and link and link != 'nan':
                    stems = tuple(sorted(list(get_word_stems(med))))
                    if stems:
                        url_mapping[stems] = link
            print(f"🔗 Loaded {len(url_mapping)} custom URL mappings.")
        except Exception as e:
            print(f"⚠️ Warning: Could not load MAPPING LINKS.csv: {e}")

    # 2. Load Master Original List (310)
    orig_entries = []
    if os.path.exists(ORIGINAL_CSV):
        df_orig = pd.read_csv(ORIGINAL_CSV, sep=';')
        for _, row in df_orig.iterrows():
            name = str(row.get('Medikament', '')).strip()
            if name and name != 'nan':
                orig_entries.append({
                    'original_name': name,
                    'stems': get_word_stems(name),
                    'matched_pdf': None
                })
    print(f"📋 Loaded {len(orig_entries)} originals.")

    # 3. Build Filename -> Name mapping from old results
    prev_file_to_name = {}
    for f in RESULT_FILES:
        if os.path.exists(f):
            try:
                df = pd.read_excel(f)
                for _, row in df.iterrows():
                    source = str(row.get('Quelle', ''))
                    prod = str(row.get('Produkt', ''))
                    if source and prod and prod != 'nan':
                        fname = os.path.basename(source)
                        # Only keep if name is not junk
                        if not any(b in prod.upper() for b in ["PACKUNGSBEILAGE", "PDF", ".PDF"]):
                            prev_file_to_name[fname] = re.sub(r"\[.*?\]\s*", "", prod).strip()
            except: pass

    # 4. Audit Physical PDFs (211)
    all_results = []
    print(f"📂 Auditing physical PDFs with high-precision naming...")
    for pdf_file in os.listdir(PDF_DIR):
        if not pdf_file.endswith(".pdf"): continue
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        
        # Determine Name
        prod_name = prev_file_to_name.get(pdf_file)
        if not prod_name or any(b in prod_name.upper() for b in ["PACKUNGSBEILAGE", "PDF", "NAME MANUELL"]):
            prod_name = get_name_from_pdf(pdf_path)
            
        # Analysis
        try:
            ing_data = extract_from_pdf(pdf_path)
            analysis = analyzer.analyze(prod_name, ing_data)
            
            # 5. Populate "Problematische Stoffe" for OK status
            prob_substances = ", ".join(analysis.problematic_substances)
            if analysis.category.value == "OK" and not prob_substances:
                prob_substances = "Keine relevanten Stoffe gefunden"
            
            # Resolve URL
            # Priority 1: MAPPING LINKS.csv
            online_url = ""
            res_stems = tuple(sorted(list(get_word_stems(prod_name))))
            if res_stems in url_mapping:
                online_url = url_mapping[res_stems]
            
            # Priority 2: Reconstruct BASG URL
            if not online_url:
                if re.match(r"\d+-\d+\.pdf", pdf_file):
                    online_url = f"https://medikamente.basg.gv.at/documents/{pdf_file}"
                elif pdf_file.startswith("AU_"):
                    online_url = "(PDF lokal vorhanden)"

            all_results.append({
                'Produkt': prod_name,
                'Kategorie': analysis.category.value,
                'Grund für Einstufung': analysis.reason,
                'Problematische Stoffe': prob_substances,
                'Warnung': "Ja" if analysis.dosage_warning else "Nein",
                'Quelle': online_url or f"(PDF vorhanden: {pdf_file})",
                'stems': get_word_stems(prod_name)
            })
        except: pass

    # 6. Audit original matches & [NEU] tagging
    matched_indices = set()
    for orig in orig_entries:
        best_idx, best_score = -1, 0
        for idx, res in enumerate(all_results):
            shared = orig['stems'].intersection(res['stems'])
            if shared:
                score = len(shared) / len(orig['stems']) if orig['stems'] else 0
                if score >= 0.5 and score > best_score:
                    best_score, best_idx = score, idx
        if best_idx != -1:
            orig['matched_pdf'] = all_results[best_idx]
            matched_indices.add(best_idx)
    
    for idx, res in enumerate(all_results):
        if idx not in matched_indices:
            res['Produkt'] = f"[NEU] {res['Produkt']}"

    # 7. Final Export
    print(f"📊 Creating Final Audited Master: {OUTPUT_XLSX}")
    with pd.ExcelWriter(OUTPUT_XLSX, engine='xlsxwriter') as writer:
        df_res = pd.DataFrame(all_results).drop(columns=['stems']).drop_duplicates('Produkt')
        
        # Sort and Format
        cat_order = {"Nicht koscher": 0, "Nicht für Pessach": 1, "Verdacht Chometz": 2, "OK": 3}
        df_res['cat_sort'] = df_res['Kategorie'].map(cat_order).fillna(4)
        df_res = df_res.sort_values(['cat_sort', 'Produkt']).drop(columns=['cat_sort'])
        df_res.to_excel(writer, index=False, sheet_name='Analyseergebnisse')

        pd.DataFrame([{'Produkt (Fehlt)': o['original_name']} for o in orig_entries if not o['matched_pdf']]).to_excel(writer, index=False, sheet_name='Suche_Ergebnislos')

        legend_data = {
            'Status / Begriff': [
                'OK', 'Nicht für Pessach', 'Verdacht Chometz', 'Nicht koscher',
                'Stufe 1 (Violett)', 'Stufe 2 (Hellrot)', 'Stufe 3 (Gelb)', 'Warnung: Darreichung', '[NEU] Tag'
            ],
            'Beschreibung / Bedeutung': [
                'Produkt ist nach Analyse der Inhaltsstoffe sicher für Pessach.',
                'Enthält problematische Stoffe (z.B. Kitniyot-Abkömmlinge wie Glukose, Sorbitol).',
                'Enthält unklare Stärken (potenzielles Chometz).',
                'Enthält tierische Bestandteile (z.B. Gelatine) - Nicht koscher.',
                'Höchste Relevanz: Gelatine, Schellack.',
                'Mittlere Relevanz: Glukose, Glycerin, Gluten.',
                'Unspezifierte Inhaltsstoffe: Stärke, modifizierte Stärke.',
                'Sirup/Tropfen/Vitamine können zusätzliche Füllstoffe enthalten.',
                'Dieses Medikament war nicht in Ihrer ursprünglichen Liste enthalten.'
            ]
        }
        pd.DataFrame(legend_data).to_excel(writer, index=False, sheet_name='Legende_Hilfe')

        # Formatting
        workbook = writer.book
        h_f = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
        w_f = workbook.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
        ok_f = workbook.add_format({'bg_color': '#E2EFDA', 'font_color': '#375623', 'border': 1, 'text_wrap': True})
        nfp_f = workbook.add_format({'bg_color': '#FCE4D6', 'font_color': '#833C0C', 'border': 1, 'text_wrap': True})
        vc_f = workbook.add_format({'bg_color': '#FFF2CC', 'font_color': '#7F6000', 'border': 1, 'text_wrap': True})
        nk_f = workbook.add_format({'bg_color': '#EAD1DC', 'font_color': '#4C1130', 'border': 1, 'text_wrap': True})

        sheet = writer.sheets['Analyseergebnisse']
        sheet.freeze_panes(1, 1)
        widths = [45, 20, 55, 45, 12, 60]
        for c, w in enumerate(widths):
            sheet.set_column(c, c, w, w_f)
            sheet.write(0, c, df_res.columns[c], h_f)
            
        nr = len(df_res)
        sheet.conditional_format(1, 1, nr, 1, {'type': 'text', 'criteria': 'containing', 'value': 'OK', 'format': ok_f})
        sheet.conditional_format(1, 1, nr, 1, {'type': 'text', 'criteria': 'containing', 'value': 'Nicht für Pessach', 'format': nfp_f})
        sheet.conditional_format(1, 1, nr, 1, {'type': 'text', 'criteria': 'containing', 'value': 'Verdacht Chometz', 'format': vc_f})
        sheet.conditional_format(1, 1, nr, 1, {'type': 'text', 'criteria': 'containing', 'value': 'Nicht koscher', 'format': nk_f})
        sheet.autofilter(0, 0, nr, 5)

    print(f"✅ V10 Precision Audit Complete! Total Identified: {len(df_res)}")

if __name__ == "__main__":
    main()
