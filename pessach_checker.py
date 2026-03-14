import os
import asyncio
import pandas as pd
import fitz  # PyMuPDF
import re
from flashtext import KeywordProcessor
import logging
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CSV_PATH = r"C:\Users\bingu\Desktop\PESSACH PROJECT\Koscher_Medikamente_Pessach.csv"
OUTPUT_PATH = r"C:\Users\bingu\Desktop\PESSACH PROJECT\Pessach_Medikamente_AT_Final.xlsx"
PDF_TEMP_DIR = r"C:\Users\bingu\Desktop\PESSACH PROJECT\temp_pdfs"

# Ensure temp dir exists
os.makedirs(PDF_TEMP_DIR, exist_ok=True)

# Analysis Keywords
SAFE_KEYWORDS = ["maisstärke", "dextrin", "maltodextrin"]
LEVEL_1_KEYWORDS = ["gelatine", "shellac", "schellack"]
LEVEL_2_KEYWORDS = [
    "sorbit", "sorbitol", "dextrose", "glucose", "glukose", "glycerin", "glycerol",
    "weizen", "gerste", "roggen", "hafer", "dinkel", "wheat", "barley", "rye", "oat", "spelt",
    "gluten", "wheat starch", "wheat gluten", "wheat protein", "hydrolyzed wheat protein",
    "wheat germ", "wheat extract", "barley extract", "barley malt", "barley starch",
    "oat starch", "oat flour", "avena extract", "rye starch", "rye flour", "spelt starch", "spelt flour"
]
LEVEL_3_KEYWORDS = [
    "stärke", "starch", "pregelatinized starch", "modified starch", "carboxymethylstärke",
    "sodium starch glycolate", "hydrolysed starch", "stärkehydrolysat", "starch derivative",
    "carboxymethylstärke-natrium", "stärkeglykolat", "natriumstärkeglykolat"
]
DOSAGE_WARNING_KEYWORDS = ["sirup", "tropfen", "vitamin"]

class PessachAnalyzer:
    def __init__(self):
        self.masker = KeywordProcessor()
        for kw in SAFE_KEYWORDS:
            self.masker.add_keyword(kw, "safe_starch_placeholder")
        
        self.categorizer = KeywordProcessor()
        for kw in LEVEL_1_KEYWORDS: self.categorizer.add_keyword(kw, ("Level 1", kw))
        for kw in LEVEL_2_KEYWORDS: self.categorizer.add_keyword(kw, ("Level 2", kw))
        for kw in LEVEL_3_KEYWORDS: self.categorizer.add_keyword(kw, ("Level 3", kw))

    def analyze_text(self, text, filename_or_url):
        text_lower = text.lower()
        masked_text = self.masker.replace_keywords(text_lower)
        found_items = self.categorizer.extract_keywords(masked_text)

        category = "OK"
        problematic_substances = []
        highest_level = 4
        reason = "Keine problematischen Inhaltsstoffe gefunden."

        for level_str, kw in found_items:
            level = int(level_str.split()[1])
            if level < highest_level:
                highest_level = level
                if level == 1: 
                    category = "Nicht koscher"
                    reason = f"Enthält Substanz der Stufe 1: {kw}"
                elif level == 2: 
                    category = "Nicht für Pessach"
                    reason = f"Enthält Substanz der Stufe 2: {kw}"
                elif level == 3: 
                    category = "Verdacht Chometz"
                    reason = f"Enthält unklare Stärke (Stufe 3): {kw}"
            problematic_substances.append(kw)

        problematic_str = ", ".join(sorted(list(set(problematic_substances))))
        warning_dosage = any(kw in filename_or_url.lower() for kw in DOSAGE_WARNING_KEYWORDS)
        if warning_dosage:
            reason = reason + " (Warnung: Darreichungsform prüfen)"
        
        return category, problematic_str, "Ja" if warning_dosage else "Nein", reason

def extract_ingredients_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        
        fi_pattern = re.compile(r"6\.1\s+Liste\s+der\s+sonstigen\s+Bestandteile(.*?)(?=6\.2)", re.S | re.I)
        match = fi_pattern.search(full_text)
        if match: return match.group(1).strip()
            
        gi_pattern = re.compile(r"6\.\s+Inhalt\s+der\s+Packung.*?(?:Was.*?enth\u00e4lt|Die\s+sonstigen\s+Bestandteile\s+sind:)(.*?)(?=Wie\s+.*?aussieht|Pharmazeutischer\s+Unternehmer|7\.\s+|8\.\s+)", re.S | re.I)
        match = gi_pattern.search(full_text)
        if match: return match.group(1).strip()
            
        last_resort = re.compile(r"sonstigen\s+Bestandteile\s+(?:sind|enthalten|:)(.*?)(?:\d\.|Wie\s+|Pharmazeutischer|$)", re.S | re.I)
        match = last_resort.search(full_text)
        if match: return match.group(1).strip()

        return "Bereich Hilfsstoffe nicht gefunden"
    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {e}")
        return f"Fehler beim Parsen: {e}"

async def get_apotheken_umschau_pdf(med_name, session, page):
    """Fallback high-speed PDF scraper for Apotheken Umschau."""
    async def try_au_search(query):
        try:
            logger.info(f"AU Search (PDF): '{query}'")
            search_url = f"https://www.apotheken-umschau.de/suche/?query={query.replace(' ', '+')}&type=beipackzettel"
            await page.goto(search_url)
            
            # Consent
            try:
                consent = page.locator('button:has-text("Zustimmen")')
                if await consent.is_visible(timeout=2000): await consent.click()
            except: pass

            # Links
            links = page.locator('a[href*="/medikamente/beipackzettel/"]')
            if await links.count() == 0: return None
            
            target_url = None
            for i in range(await links.count()):
                href = await links.nth(i).get_attribute("href")
                # Specific product pages are long and don't end with /beipackzettel/
                if href and len(href) > 40 and "/beipackzettel/" in href and not href.endswith("/beipackzettel/"):
                    target_url = href if href.startswith("http") else f"https://www.apotheken-umschau.de{href}"
                    break
            
            if not target_url: return None
            
            logger.info(f"AU Product Page: {target_url}")
            await page.goto(target_url)
            await asyncio.sleep(1)
            
            # Find PDF link in "PDF-Dokumente" section or by text
            # We look for the "Original Beipackzettel" specifically
            pdf_link_loc = page.locator('a:has-text("Original Beipackzettel"), a[href$=".pdf"]')
            if await pdf_link_loc.count() > 0:
                pdf_url = await pdf_link_loc.first.get_attribute("href")
                if not pdf_url.startswith("http"): pdf_url = "https://www.apotheken-umschau.de" + pdf_url
                
                logger.info(f"Downloading AU PDF: {pdf_url}")
                pdf_resp = session.get(pdf_url)
                if pdf_resp.status_code == 200:
                    pdf_filename = re.sub(r'[^a-zA-Z0-9]', '_', query) + ".pdf"
                    pdf_path = os.path.join(PDF_TEMP_DIR, pdf_filename)
                    with open(pdf_path, 'wb') as f: f.write(pdf_resp.content)
                    return pdf_path, pdf_url
            
            return None
        except Exception as e:
            logger.error(f"AU PDF Scrape error for '{query}': {e}")
            return None

    # Step 1: Specific Name
    res = await try_au_search(med_name)
    if res: return res
    
    # Step 2: Brand Fallback
    brand = med_name.split()[0]
    if brand != med_name:
        logger.info(f"AU Brand Fallback: {brand}")
        return await try_au_search(brand)
    
    return None

async def main():
    analyzer = PessachAnalyzer()
    existing_results = []
    
    if os.path.exists(OUTPUT_PATH):
        logger.info(f"Loading existing results from {OUTPUT_PATH}")
        xls = pd.ExcelFile(OUTPUT_PATH)
        for sheet in xls.sheet_names:
            df_sheet = pd.read_excel(xls, sheet_name=sheet)
            existing_results.extend(df_sheet.to_dict('records'))
    
    if existing_results:
        # Re-process failures
        to_process = [r for r in existing_results if r['Kategorie'] in ['Kein Ergebnis in Suche', 'Kein PDF gefunden', 'API_ERROR']]
        successful = [r for r in existing_results if r['Kategorie'] not in ['Kein Ergebnis in Suche', 'Kein PDF gefunden', 'API_ERROR']]
        logger.info(f"Retrying {len(to_process)} failed items. {len(successful)} already success.")
    else:
        df_input = pd.read_csv(CSV_PATH, sep=';')
        to_process = [{"Produkt": m} for m in df_input['Medikament'].tolist()]
        successful = []
        logger.info(f"Fresh run for {len(to_process)} items.")

    if not to_process:
        logger.info("Nothing to redo.")
        return

    import playwright.async_api
    async with playwright.async_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        # BASG Token Capture
        api_token = None
        async def handle_request(request):
            nonlocal api_token
            if "/api/v1/medication/search" in request.url:
                auth = request.headers.get("authorization")
                if auth and auth.startswith("Bearer "): api_token = auth
        
        page.on("request", handle_request)
        await page.goto("https://medikamente.basg.gv.at/de/medicinal-products")
        await asyncio.sleep(2)
        
        cookies = await context.cookies()
        session = requests.Session()
        for cookie in cookies: session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
        basg_headers = {"Authorization": api_token if api_token else "", "Accept-Language": "DE", "Content-Type": "application/json"}

        final_results = successful
        for entry in to_process:
            med_name = str(entry['Produkt']).replace("[NEU] ", "").replace("[AU] ", "")
            try:
                found = False
                # 1. BASG PDF (via API)
                if api_token:
                    logger.info(f"BASG Check: {med_name}")
                    payload = {"nameAuthNumber": med_name}
                    resp = session.post("https://medikamente.basg.gv.at/api/api/v1/medication/search?page=1&size=10", json=payload, headers=basg_headers)
                    if resp.status_code == 200:
                        items = resp.json().get("items", [])
                        if items:
                            item = items[0]
                            pdf_type = (item.get("packageLeaflet") or item.get("fachInformation") or {}).get("type")
                            if item.get("authNumber") and pdf_type:
                                pdf_url = f"https://medikamente.basg.gv.at/documents/{item.get('authNumber')}__{pdf_type}.pdf"
                                r_pdf = session.get(pdf_url)
                                if r_pdf.status_code == 200:
                                    path = os.path.join(PDF_TEMP_DIR, f"{item.get('authNumber')}.pdf")
                                    with open(path, 'wb') as f: f.write(r_pdf.content)
                                    text = extract_ingredients_from_pdf(path)
                                    cat, prob, warn, reason = analyzer.analyze_text(text, med_name)
                                    final_results.append({"Produkt": f"[NEU] {item.get('name')}", "Kategorie": cat, "Grund für Einstufung": reason, "Gefundene Problematische Stoffe": prob, "Warnung Darreichungsform": warn, "Hilfsstoffe": text, "Quelle": pdf_url})
                                    found = True

                # 2. Apotheken Umschau PDF Fallback
                if not found:
                    res = await get_apotheken_umschau_pdf(med_name, session, page)
                    if res:
                        pdf_path, pdf_url = res
                        text = extract_ingredients_from_pdf(pdf_path)
                        cat, prob, warn, reason = analyzer.analyze_text(text, med_name)
                        final_results.append({"Produkt": f"[AU] {med_name}", "Kategorie": cat, "Grund für Einstufung": reason, "Gefundene Problematische Stoffe": prob, "Warnung Darreichungsform": warn, "Hilfsstoffe": text, "Quelle": pdf_url})
                    else:
                        final_results.append(entry)
            except Exception as e:
                logger.error(f"Error {med_name}: {e}")
                final_results.append(entry)

        await browser.close()

    # Export
    df = pd.DataFrame(final_results)
    with pd.ExcelWriter(OUTPUT_PATH, engine='xlsxwriter') as writer:
        df[~df['Kategorie'].isin(['Kein Ergebnis in Suche', 'Kein PDF gefunden', 'API_ERROR'])].to_excel(writer, sheet_name='Analyse Erfolgreich', index=False)
        df[df['Kategorie'] == 'Kein PDF gefunden'].to_excel(writer, sheet_name='Kein PDF gefunden', index=False)
        df[df['Kategorie'] == 'Kein Ergebnis in Suche'].to_excel(writer, sheet_name='Suche ohne Ergebnis', index=False)
        for sh in writer.sheets:
            w = writer.sheets[sh]
            w.set_column('A:A', 40); w.set_column('B:B', 20); w.set_column('C:C', 50); w.set_column('D:D', 40); w.set_column('E:E', 15); w.set_column('F:G', 60)
    logger.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
