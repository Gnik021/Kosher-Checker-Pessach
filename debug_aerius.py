import asyncio
import os
import playwright.async_api
import logging
import requests
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PDF_TEMP_DIR = "debug_pdfs"
os.makedirs(PDF_TEMP_DIR, exist_ok=True)

class PessachAnalyzer:
    def analyze_text(self, text, med_name):
        return "DEBUG_OK", "none", "no", "debug_reason"

async def get_apotheken_umschau_data(med_name, page):
    async def try_au_search(query):
        try:
            logger.info(f"AU Search (HTML): '{query}'")
            search_url = f"https://www.apotheken-umschau.de/suche/?query={query.replace(' ', '+')}&type=beipackzettel"
            await page.goto(search_url)
            
            # Consent
            try:
                consent = page.locator('button:has-text("Zustimmen")')
                if await consent.is_visible(timeout=3000): await consent.click()
            except: pass

            # Links
            links = page.locator('a[href*="/medikamente/beipackzettel/"]')
            if await links.count() == 0:
                logger.info("No links found")
                return None
            
            target_url = None
            for i in range(await links.count()):
                href = await links.nth(i).get_attribute("href")
                if href and len(href) > 30 and "/beipackzettel/" in href:
                    target_url = href if href.startswith("http") else f"https://www.apotheken-umschau.de{href}"
                    break
            
            if not target_url:
                logger.info("No target target_url found in links")
                return None
            
            logger.info(f"AU Product Page: {target_url}")
            await page.goto(target_url)
            await asyncio.sleep(2)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            ingredients = ""
            # Strategy 1: Look for "Zusammensetzung" or "Inhaltsstoffe" headers
            headers = soup.find_all(['h2', 'h3', 'h4', 'strong', 'span'])
            for h in headers:
                text = h.get_text().lower()
                if ("was" in text and "enthält" in text) or ("zusammensetzung" in text) or ("bestandteile" in text):
                    logger.info(f"Found header: {text}")
                    sibling = h.find_next(['p', 'ul', 'div', 'table'])
                    if sibling:
                        ingredients = sibling.get_text(separator=' ').strip()
                        if ingredients: break
            
            if not ingredients:
                logger.info("Trying general text match...")
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    text = main_content.get_text(separator=' ')
                    match = re.search(r"(?:was.*?enth\xf4lt|zusammensetzung|bestandteile).*?(\d\.|wie|$)", text, re.S | re.I)
                    if match:
                        ingredients = match.group(0).strip()

            if ingredients:
                logger.info(f"Extracted ingredients (first 100 chars): {ingredients[:100]}")
                return ingredients, target_url
            
            return None
        except Exception as e:
            logger.error(f"AU HTML Scrape error for '{query}': {e}")
            return None

    res = await try_au_search(med_name)
    if not res:
        brand = med_name.split()[0]
        res = await try_au_search(brand)
    return res

async def debug_main():
    async with playwright.async_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        res = await get_apotheken_umschau_data("Aerius", page)
        print("\nRESULT:", res)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_main())
