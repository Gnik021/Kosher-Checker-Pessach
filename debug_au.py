import asyncio
import os
import playwright.async_api
import logging
import requests
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PDF_TEMP_DIR = "debug_pdfs"
os.makedirs(PDF_TEMP_DIR, exist_ok=True)

async def debug_au(med_name):
    async with playwright.async_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        url = "https://www.apotheken-umschau.de/medikamente/beipackzettel/"
        await page.goto(url)
        await asyncio.sleep(2)
        
        # Take screenshot
        await page.screenshot(path="debug_au_start.png")
        
        # Click cookie banner
        try:
            banner = page.locator('button:has-text("Zustimmen"), button:has-text("Akzeptieren")')
            if await banner.is_visible():
                await banner.click()
                logger.info("Clicked cookie banner")
        except: pass

        # Find search input
        # Let's try to be more specific
        search_input = page.locator('input#search-input-field, input[placeholder*="Medikament"], input[type="search"]')
        if await search_input.count() == 0:
             logger.error("Could not find search input")
             await browser.close()
             return

        await search_input.first.fill(med_name)
        await page.screenshot(path="debug_au_typed.png")
        await search_input.first.press("Enter")
        
        await asyncio.sleep(5) # Wait for results
        await page.screenshot(path="debug_au_results.png")
        
        # Check for results
        results = page.locator('a[href*="/beipackzettel/"]')
        count = await results.count()
        logger.info(f"Found {count} results")
        
        if count > 0:
            for i in range(min(count, 3)):
                text = await results.nth(i).inner_text()
                href = await results.nth(i).get_attribute("href")
                logger.info(f"Result {i}: {text} ({href})")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_au("Aerius"))
