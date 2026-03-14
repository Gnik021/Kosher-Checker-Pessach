import asyncio
import playwright.async_api
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_api():
    async with playwright.async_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        api_token = None
        
        async def handle_request(request):
            nonlocal api_token
            if "/api/v1/medication/search" in request.url:
                auth = request.headers.get("authorization")
                if auth: api_token = auth
        
        page.on("request", handle_request)
        await page.goto("https://medikamente.basg.gv.at/de/medicinal-products")
        await page.locator('label:has-text("Bezeichnung / Zulassungsnummer")').click()
        await page.keyboard.type("Aspirin")
        await page.keyboard.press("Enter")
        await page.locator('button:has-text("Suche")').first.click()
        
        for _ in range(10):
            if api_token: break
            await asyncio.sleep(1.0)
        
        await browser.close()

    if not api_token:
        print("Token failed")
        return

    headers = {"Authorization": api_token, "Content-Type": "application/json"}
    payload = {"nameAuthNumber": "Aspirin"}
    resp = requests.post("https://medikamente.basg.gv.at/api/api/v1/medication/search?page=1&size=5", json=payload, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", [])
        if items:
            print(json.dumps(items[0], indent=2))
        else:
            print("No items found")
    else:
        print(f"Error {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    asyncio.run(debug_api())
