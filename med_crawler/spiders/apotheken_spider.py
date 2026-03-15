"""
Apotheken-Umschau Spider - Fallback Scraper for medications missing from the main register.
Optimized for high-speed HTML crawling and PDF extraction.
"""

import scrapy
import re
import os
from typing import List, Optional
from ..models import IngredientData, ConfidenceScore
from ..logic import PessachAnalyzer, extract_from_pdf
from ..utils import normalize_med_name

class ApothekenSpider(scrapy.Spider):
    """
    Spider for searching Apotheken-Umschau and extracting patient leaflets.
    Used as a fallback when the official BASG register lacks data.
    """
    name = "apotheken"
    allowed_domains = ["apotheken-umschau.de"]
    
    def __init__(self, medications: str = None, *args, **kwargs):
        super(ApothekenSpider, self).__init__(*args, **kwargs)
        
        v12_path = r"C:\Users\bingu\Desktop\PESSACH PROJECT\V12.csv"
        self.med_list = []
        if os.path.exists(v12_path):
            try:
                with open(v12_path, 'r', encoding='cp1252') as f:
                    lines = f.readlines()
                self.med_list = [l.strip() for l in lines[1:] if l.strip()]
                self.logger.info(f"Loaded {len(self.med_list)} meds from V12.csv via text read")
            except Exception as e:
                self.logger.error(f"Failed to load V12.csv: {e}")
        else:
            self.logger.error(f"V12.csv not found at {v12_path}")
            
        self.pdf_temp_dir = r"C:\Users\bingu\Desktop\PESSACH PROJECT\temp_pdfs"
        self.analyzer = PessachAnalyzer()
        os.makedirs(self.pdf_temp_dir, exist_ok=True)

    def start_requests(self):
        """Generates initial search requests for each medication."""
        for med in self.med_list:
            variants = normalize_med_name(med)
            yield self.make_search_request(med, variants)

    def make_search_request(self, original_name: str, variants: List[str]):
        """Creates a search request for the next available variant."""
        if not variants:
            return None
            
        current_variant = variants[0]
        remaining = variants[1:]
        
        search_url = f"https://www.apotheken-umschau.de/suche/?query={current_variant.replace(' ', '+')}&type=beipackzettel"
        return scrapy.Request(
            url=search_url,
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
        # Find links to product pages
        detail_links = response.css('a[href*="/medikamente/beipackzettel/"]::attr(href)').getall()
        
        target_path = None
        for path in detail_links:
            if len(path) > 40 and not path.endswith("/beipackzettel/"):
                target_path = path
                break
        
        if target_path:
            yield scrapy.Request(
                url=response.urljoin(target_path),
                callback=self.parse_product_page,
                cb_kwargs={"med_name": original_name}
            )
        elif remaining_variants:
            self.logger.info(f"0 results on AU for '{current_variant}'. Retrying with '{remaining_variants[0]}'...")
            yield self.make_search_request(original_name, remaining_variants)
        else:
            self.logger.info(f"No results found on AU for all variants of: {original_name}")

    def parse_product_page(self, response, med_name: str):
        """Identifies and schedules the download of the 'Original Beipackzettel' PDF."""
        # Priority 1: Text-based lookup for the PDF link
        pdf_url = response.xpath('//a[contains(text(), "Original Beipackzettel")]/@href').get()
        
        # Priority 2: Generic PDF link lookup
        if not pdf_url:
            pdf_url = response.css('a[href$=".pdf"]::attr(href)').get()
        
        if pdf_url:
            yield scrapy.Request(
                url=response.urljoin(pdf_url),
                callback=self.parse_pdf,
                cb_kwargs={"med_name": med_name, "pdf_url": response.urljoin(pdf_url)}
            )
        else:
            self.logger.warning(f"Product page found but PDF link is missing for: {med_name}")

    def parse_pdf(self, response, med_name: str, pdf_url: str):
        """Saves the PDF and performs the ingredient analysis."""
        clean_filename = re.sub(r'[^a-zA-Z0-9]', '_', med_name)
        file_path = os.path.join(self.pdf_temp_dir, f"AU_{clean_filename}.pdf")
        
        with open(file_path, 'wb') as f:
            f.write(response.body)
        
        # Skill-driven enrichment: Professional extraction and analysis
        ingredient_data = extract_from_pdf(file_path)
        ingredient_data.source_url = pdf_url
        
        analysis_result = self.analyzer.analyze(med_name, ingredient_data)
        
        yield {
            "original_name": med_name,
            "actual_name": f"[AU] {med_name}",
            "result": analysis_result.model_dump(),
            "confidence": ingredient_data.confidence
        }
