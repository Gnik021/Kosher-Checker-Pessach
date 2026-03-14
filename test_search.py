import asyncio
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
import logging

logging.basicConfig(level=logging.INFO)

async def test():
    crawler = PlaywrightCrawler()
    @crawler.router.default_handler
    async def h(context: PlaywrightCrawlingContext):
        page = context.page
        await page.goto("https://medikamente.basg.gv.at/de/medicinal-products")
        await asyncio.sleep(3)
        
        # Click label
        label = page.locator('label:has-text("Bezeichnung / Zulassungsnummer")')
        await label.click()
        await asyncio.sleep(0.5)
        
        # Type via keyboard instead of fill (often more reliable for Angular)
        await page.keyboard.type("Aerius")
        await asyncio.sleep(1)
        
        # Click Suche
        btn = page.locator('button.mat-mdc-raised-button.mat-primary:has-text("Suche")')
        await btn.click()
        
        await asyncio.sleep(5)
        rows = await page.locator('mat-row').count()
        print(f"--- RESULTS COUNT FOR AERIUS: {rows} ---")
        
        if rows > 0:
            txt = await page.locator('mat-row').first.inner_text()
            print(f"First result: {txt.splitlines()[0]}")

    await crawler.run(["https://medikamente.basg.gv.at/de/medicinal-products"])

if __name__ == "__main__":
    asyncio.run(test())
