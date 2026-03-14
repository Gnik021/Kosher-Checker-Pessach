import asyncio
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee import Request
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    crawler = PlaywrightCrawler()

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext):
        page = context.page
        await page.goto("https://medikamente.basg.gv.at/de/medicinal-products")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="debug_step1_home.png")
        
        med_name = "Aspirin"
        await page.fill('input[role="combobox"]', med_name)
        await page.screenshot(path="debug_step2_filled.png")
        
        await page.click('button.mat-mdc-raised-button.mat-primary:has-text("Suche")')
        await asyncio.sleep(5)
        await page.screenshot(path="debug_step3_after_click.png")
        
        try:
            await page.wait_for_selector('mat-row', timeout=10000)
            print("Found mat-row!")
        except Exception as e:
            print(f"Failed to find mat-row: {e}")
            
        await page.screenshot(path="debug_step4_final.png")

    await crawler.run([Request(url="https://medikamente.basg.gv.at/de/medicinal-products", unique_key="debug")])

if __name__ == "__main__":
    asyncio.run(main())
