"""
Pessach Medication Checker 2.0 - Orchestrator
Coordinates the multi-source scraping and analysis pipeline.
"""

import os
import re
import json
import logging
import subprocess
import pandas as pd
from typing import List, Dict, Any

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Orchestrator")

# Constants
PROJECT_DIR = r"C:\Users\bingu\Desktop\PESSACH PROJECT"
INPUT_CSV = os.path.join(PROJECT_DIR, "test_recovery_batch.csv")
OUTPUT_xlsx = os.path.join(PROJECT_DIR, "Pessach_Medikamente_2.0.xlsx")
MISSING_MEDS_FILE = os.path.join(PROJECT_DIR, "missing_meds.txt")
BASG_JSON = os.path.join(PROJECT_DIR, "basg_results.json")
AU_JSON = os.path.join(PROJECT_DIR, "au_results.json")

def run_spider(spider_name: str, output_file: str, extra_args: List[str] = None):
    """Executes a Scrapy spider as a subprocess."""
    cmd = ["scrapy", "crawl", spider_name, "-O", output_file]
    if extra_args:
        cmd.extend(extra_args)
    
    logger.info(f"Launching spider: {spider_name}...")
    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        logger.info(f"Spider {spider_name} completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Spider {spider_name} failed with exit code {e.returncode}")

def load_json_results(file_path: str) -> List[Dict[str, Any]]:
    """Safe data loader for Scrapy JSON exports."""
    if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
    return []

# Additional Constants for delta run
EXISTING_RESULTS_xlsx = os.path.join(PROJECT_DIR, "Pessach_Medikamente_AT_Final.xlsx")

def main():
    # 1. Verification of inputs
    if not os.path.exists(INPUT_CSV):
        logger.error(f"Input file missing: {INPUT_CSV}")
        return

    # 2. Identify missing medications by comparing with AT_Final
    df_input = pd.read_csv(INPUT_CSV, sep=';')
    all_meds = set(df_input['Medikament'].tolist())
    
    found_meds = set()
    if os.path.exists(EXISTING_RESULTS_xlsx):
        try:
            df_existing = pd.read_excel(EXISTING_RESULTS_xlsx)
            # Remove prefixes like [NEU] or [AU] for comparison
            raw_found = df_existing['Produkt'].astype(str).tolist()
            for m in raw_found:
                clean_m = re.sub(r"\[.*?\]\s*", "", m).strip()
                found_meds.add(clean_m)
        except Exception as e:
            logger.error(f"Failed to read existing results: {e}")
    
    # Intelligent check: also check if they are already in our 2.0 output
    if os.path.exists(OUTPUT_xlsx):
        try:
            df_20 = pd.read_excel(OUTPUT_xlsx)
            raw_found_2 = df_20['Produkt'].astype(str).tolist()
            for m in raw_found_2:
                clean_m = re.sub(r"\[.*?\]\s*", "", m).strip()
                found_meds.add(clean_m)
        except: pass

    # Filter for medications that really haven't been found yet
    missing_meds = [m for m in all_meds if m not in found_meds]
    logger.info(f"Consolidated check: {len(found_meds)} found, {len(missing_meds)} still missing.")
    
    if not missing_meds:
        logger.info("No missing medications to process. Everything is caught up!")
        return

    # Write the target list for the spiders
    with open(MISSING_MEDS_FILE, 'w', encoding='utf-8') as f:
        for m in missing_meds:
            f.write(f"{m}\n")

    # 3. Phase 1: BASG Search with Brain (Normalization)
    logger.info(f"=== Phase 1: BASG Intelligent Search ({len(missing_meds)} meds) ===")
    run_spider("basg", BASG_JSON)
    
    # Reload processed to see if we found more
    basg_results = load_json_results(BASG_JSON)
    found_in_basg = {r['original_name'] for r in basg_results}
    
    still_missing = [m for m in missing_meds if m not in found_in_basg]

    # 4. Phase 2: Apotheken-Umschau Fallback with Brain
    if still_missing:
        logger.info(f"=== Phase 2: AU Intelligent Fallback ({len(still_missing)} still missing) ===")
        with open(MISSING_MEDS_FILE, 'w', encoding='utf-8') as f:
            for m in still_missing:
                f.write(f"{m}\n")
        
        run_spider("apotheken", AU_JSON)
    else:
        logger.info("All selected medications found in BASG. Skipping AU.")

    # 5. Data Consolidation
    logger.info("=== Phase 3: Data Consolidation & Export ===")
    au_results = load_json_results(AU_JSON)
    all_raw_results = basg_results + au_results
    
    if not all_raw_results:
        logger.warning("No data extracted. Export cancelled.")
        return

    # Transform to flat format for Excel
    processed_rows = []
    for entry in all_raw_results:
        res = entry['result']
        processed_rows.append({
            "Produkt": entry['actual_name'],
            "Kategorie": res['category'],
            "Analyse-Grund": res['reason'],
            "Problematische Stoffe": ", ".join(res['problematic_substances']),
            "Darreichung_Warnung": "Ja" if res['dosage_warning'] else "Nein",
            "Scraping_Confidence": entry['confidence'],
            "Quelle": res['source']
        })
    
    # 6. Professional Excel Export
    df_final = pd.DataFrame(processed_rows)
    try:
        with pd.ExcelWriter(OUTPUT_xlsx, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name="Full Analysis")
            workbook = writer.book
            worksheet = writer.sheets["Full Analysis"]
            
            # Formatting
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            for col_num, value in enumerate(df_final.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            worksheet.set_column('A:A', 35) # Produkt
            worksheet.set_column('B:B', 20) # Kategorie
            worksheet.set_column('C:C', 50) # Grund
            worksheet.set_column('D:D', 40) # Stoffe
            worksheet.set_column('E:G', 20) # Warn/Conf/Quell
            
        logger.info(f"Professional report successfully saved to: {OUTPUT_xlsx}")
    except Exception as e:
        logger.error(f"Failed to export Excel: {e}")

    # Cleanup temporary run files
    for tmp_file in [BASG_JSON, AU_JSON, MISSING_MEDS_FILE]:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

if __name__ == "__main__":
    main()
