import asyncio
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
import logging
import os

logging.basicConfig(level=logging.INFO)

async def test():
    crawler = PlaywrightCrawler()
    @crawler.router.default_handler
    async def h(context: PlaywrightCrawlingContext):
        page = context.page
        term = "Aspirin + C Brausetabletten"
        await page.goto("https://medikamente.basg.gv.at/de/medicinal-products")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # Click label
        await page.locator('label:has-text("Bezeichnung / Zulassungsnummer")').click()
        await asyncio.sleep(0.5)
        
        # Typing
        await page.keyboard.type(term, delay=100)
        await asyncio.sleep(1)
        await page.screenshot(path="search_typed.png")
        
        # Press Enter
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        await page.screenshot(path="after_enter.png")
        
        # Click Suche Button
        btn = page.locator('button.mat-mdc-raised-button.mat-primary:has-text("Suche")')
        await btn.click()
        
        await asyncio.sleep(5)
        await page.screenshot(path="after_button_click.png")
        
        rows = await page.locator('mat-row').count()
        print(f"--- RESULTS COUNT FOR '{term}': {rows} ---")

    await crawler.run(["https://medikamente.basg.gv.at/de/medicinal-products"])

if __name__ == "__main__":
    asyncio.run(test())
