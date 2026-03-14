"""
BASG Spider - Multi-phase Scraper for the Austrian Medicines Register.
Handles Bearer token discovery and medication data extraction.
"""

import scrapy
import json
import pandas as pd
import os
import time
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright
from ..models import MedicationRecord, AnalysisResult, SuitabilityCategory, IngredientData, ConfidenceScore
from ..logic import PessachAnalyzer, extract_from_pdf
from ..utils import normalize_med_name

class BasgSpider(scrapy.Spider):
    """
    Spider for searching the BASG (Austrian Medicines Register) API.
    Uses Playwright for initial authentication token capture.
    """
    name = "basg"
    allowed_domains = ["medikamente.basg.gv.at"]
    
    def __init__(self, input_csv: str = None, *args, **kwargs):
        super(BasgSpider, self).__init__(*args, **kwargs)
        self.input_csv = input_csv or r"C:\Users\bingu\Desktop\PESSACH PROJECT\Koscher_Medikamente_Pessach.csv"
        self.pdf_temp_dir = r"C:\Users\bingu\Desktop\PESSACH PROJECT\temp_pdfs"
        self.analyzer = PessachAnalyzer()
        self.token = None
        
        os.makedirs(self.pdf_temp_dir, exist_ok=True)

    def start_requests(self):
        """Initializes requests by capturing the required API token."""
        self.logger.info("Initializing BASG session and capturing token (Sync)...")
        self.token = self.get_bearer_token_sync()
        
        if not self.token:
            self.logger.error("Failed to capture Authorization token from BASG. Aborting spider.")
            return

        try:
            # We assume input is passed as argument or we read from missing_meds.txt
            if hasattr(self, 'medications'):
                meds = self.medications.split(",")
            elif os.path.exists("missing_meds.txt"):
                with open("missing_meds.txt", "r", encoding="utf-8") as f:
                    meds = [line.strip() for line in f if line.strip()]
            else:
                df = pd.read_csv(self.input_csv, sep=';')
                meds = df['Medikament'].tolist()
        except Exception as e:
            self.logger.error(f"Failed to load medications: {e}")
            return
        
        for med in meds:
            variants = normalize_med_name(med)
            yield self.make_search_request(med, variants)

    def get_bearer_token_sync(self) -> str:
        """Uses Sync Playwright to capture the Bearer token."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            token = None
            
            def handle_request(request):
                nonlocal token
                if "/api/v1/medication/search" in request.url:
                    auth = request.headers.get("authorization")
                    if auth and auth.startswith("Bearer "):
                        token = auth
            
            page.on("request", handle_request)
            try:
                page.goto("https://medikamente.basg.gv.at/de/medicinal-products", wait_until="networkidle", timeout=30000)
                # Wait up to 5 seconds for the token to appear
                for _ in range(10):
                    if token: break
                    time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Sync Playwright token capture failed: {e}")
            finally:
                browser.close()
            return token

    def make_search_request(self, original_name: str, variants: List[str]):
        """Creates a search request for the next available variant."""
        if not variants:
            return None
        
        current_variant = variants[0]
        remaining = variants[1:]
        
        return scrapy.Request(
            url="https://medikamente.basg.gv.at/api/api/v1/medication/search?page=1&size=10",
            method="POST",
            body=json.dumps({"nameAuthNumber": current_variant}),
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
                "Accept-Language": "DE"
            },
            callback=self.parse_search,
            cb_kwargs={
                "original_name": original_name,
                "current_variant": current_variant,
                "remaining_variants": remaining
            },
            dont_filter=True
        )

    def parse_search(self, response, original_name, current_variant, remaining_variants):
        """Parses the search results and handles fallbacks to next variants."""
        try:
            data = json.loads(response.text)
            items = data.get("items", [])
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode API response for: {current_variant}")
            return
        
        if not items:
            if remaining_variants:
                self.logger.info(f"0 results for '{current_variant}'. Retrying with '{remaining_variants[0]}'...")
                yield self.make_search_request(original_name, remaining_variants)
            else:
                self.logger.info(f"No results found in BASG for all variants of: {original_name}")
            return

        # Take the most relevant item
        item = items[0]
        pdf_metadata = item.get("packageLeaflet") or item.get("fachInformation") or {}
        pdf_type = pdf_metadata.get("type")
        auth_number = item.get("authNumber")
        
        if auth_number and pdf_type:
            pdf_url = f"https://medikamente.basg.gv.at/documents/{auth_number}__{pdf_type}.pdf"
            yield scrapy.Request(
                url=pdf_url,
                callback=self.parse_pdf,
                cb_kwargs={
                    "med_name": original_name,
                    "actual_name": item.get("name"),
                    "pdf_url": pdf_url,
                    "auth_number": auth_number
                }
            )
        else:
            self.logger.warning(f"Metadata found but PDF is missing for: {item.get('name')}")

    def parse_pdf(self, response, med_name, actual_name, pdf_url, auth_number):
        """Processes the downloaded PDF and runs the analyzer."""
        file_path = os.path.join(self.pdf_temp_dir, f"{auth_number}.pdf")
        with open(file_path, 'wb') as f:
            f.write(response.body)
        
        # Skill-driven enrichment: Professional extraction and analysis
        ingredient_data = extract_from_pdf(file_path)
        ingredient_data.source_url = pdf_url
        
        analysis_result = self.analyzer.analyze(actual_name, ingredient_data)
        
        yield {
            "original_name": med_name,
            "actual_name": actual_name,
            "result": analysis_result.model_dump(),
            "confidence": ingredient_data.confidence
        }
