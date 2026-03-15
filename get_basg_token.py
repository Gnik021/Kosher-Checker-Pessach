from playwright.sync_api import sync_playwright
import time
import sys

def get_token():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        token = None
        target_url = None
        
        def handle_request(request):
            nonlocal token, target_url
            if "authorization" in request.headers:
                auth = request.headers.get("authorization")
                if auth and auth.startswith("Bearer ") and "/api/" in request.url:
                    token = auth
                    target_url = request.url
        
        page.on("request", handle_request)
        try:
            page.goto("https://medikamente.basg.gv.at/de/medicinal-products", wait_until="networkidle", timeout=30000)
            
            # Trigger a small search if token not found
            if not token:
                search_input = page.locator('input[placeholder*="Name"]').first
                if search_input.is_visible():
                    search_input.fill("Aspirin")
                    page.keyboard.press("Enter")
                    time.sleep(2)
            
            for _ in range(20):
                if token: break
                time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
        finally:
            browser.close()
        return token

if __name__ == "__main__":
    t = get_token()
    if t:
        # We'll need to modify get_token to return both, but for now let's just update the logic above
        pass

def get_token_info():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        token = None
        target_url = None
        
        def handle_request(request):
            nonlocal token, target_url
            if "authorization" in request.headers:
                auth = request.headers.get("authorization")
                if auth and auth.startswith("Bearer ") and "/api/" in request.url:
                    token = auth
                    target_url = request.url
        
        page.on("request", handle_request)
        try:
            page.goto("https://medikamente.basg.gv.at/de/medicinal-products", wait_until="networkidle", timeout=30000)
            
            # Trigger search
            search_input = page.locator('input[placeholder*="Name"]').first
            if search_input.is_visible():
                search_input.fill("Aspirin")
                page.keyboard.press("Enter")
                time.sleep(2)
            
            for _ in range(20):
                if token: break
                time.sleep(0.5)
        finally:
            browser.close()
        return token, target_url

if __name__ == "__main__":
    tok, url = get_token_info()
    if tok:
        print(f"TOKEN: {tok}")
        print(f"URL: {url}")
    else:
        sys.exit(1)
