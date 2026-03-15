"""
Core analysis logic for the Pessach Medication Checker.
Contains components for scouring ingredient lists and determining suitability.
"""

import re
import logging
from typing import List, Tuple, Union, Optional
import fitz  # PyMuPDF
from flashtext import KeywordProcessor
from .models import SuitabilityCategory, ConfidenceScore, IngredientData, AnalysisResult

logger = logging.getLogger(__name__)

# --- Categorization Keywords ---
# Substances that are strictly non-kosher (e.g., animal derived)
LEVEL_1_KEYWORDS = ["gelatine", "shellac", "schellack"]

# Substances that are likely Chometz (e.g., wheat, barley) or have high risk
LEVEL_2_KEYWORDS = [
    "sorbit", "sorbitol", "dextrose", "glucose", "glukose", "glycerin", "glycerol",
    "weizen", "gerste", "roggen", "hafer", "dinkel", "wheat", "barley", "rye", "oat", "spelt",
    "gluten", "wheat starch", "wheat gluten", "wheat protein", "hydrolyzed wheat protein",
    "wheat germ", "wheat extract", "barley extract", "barley malt", "barley starch",
    "oat starch", "oat flour", "avena extract", "rye starch", "rye flour", "spelt starch", "spelt flour"
]

# Substances that are suspected Chometz (generic starches)
LEVEL_3_KEYWORDS = [
    "stärke", "starch", "pregelatinized starch", "modified starch", "carboxymethylstärke",
    "sodium starch glycolate", "hydrolysed starch", "stärkehydrolysat", "starch derivative",
    "carboxymethylstärke-natrium", "stärkeglykolat", "natriumstärkeglykolat"
]

# Starches known to be safe (usually corn-based in context)
SAFE_KEYWORDS = ["maisstärke", "dextrin", "maltodextrin"]

# Keywords indicating specific dosage forms that require special attention
DOSAGE_WARNING_KEYWORDS = ["sirup", "tropfen", "vitamin"]

class PessachAnalyzer:
    """Intelligent analyzer to categorize medication suitability for Passover."""
    
    def __init__(self):
        self.masker = KeywordProcessor()
        for kw in SAFE_KEYWORDS:
            self.masker.add_keyword(kw, "safe_starch_placeholder")
        
        self.categorizer = KeywordProcessor()
        for kw in LEVEL_1_KEYWORDS: self.categorizer.add_keyword(kw, (1, kw))
        for kw in LEVEL_2_KEYWORDS: self.categorizer.add_keyword(kw, (2, kw))
        for kw in LEVEL_3_KEYWORDS: self.categorizer.add_keyword(kw, (3, kw))

    def analyze(self, med_name: str, ingredient_data: IngredientData) -> AnalysisResult:
        """
        Analyzes ingredient text and returns a structured result.
        
        Args:
            med_name: The name of the medication.
            ingredient_data: IngredientData object containing extracted text.
            
        Returns:
            AnalysisResult: Detailed analysis report.
        """
        text = ingredient_data.extracted_ingredients.lower()
        
        # 1. Mask safe items to avoid false positives (e.g., "Maisstärke" shouldn't trigger "Stärke")
        masked_text = self.masker.replace_keywords(text)
        
        # 2. Extract problematic substances
        found_matches: List[Tuple[int, str]] = self.categorizer.extract_keywords(masked_text)

        category = SuitabilityCategory.OK
        problematic_substances = []
        highest_severity = 4  # Lower is more severe
        reason = "Keine problematischen Inhaltsstoffe gefunden."

        for level, kw in found_matches:
            if level < highest_severity:
                highest_severity = level
                if level == 1:
                    category = SuitabilityCategory.NOT_KOSHER
                    reason = f"Enthält Substanz der Stufe 1: {kw}"
                elif level == 2:
                    category = SuitabilityCategory.NOT_PESACH
                    reason = f"Enthält Substanz der Stufe 2: {kw}"
                elif level == 3:
                    category = SuitabilityCategory.SUSPECTED_CHOMETZ
                    reason = f"Enthält unklare Stärke (Stufe 3): {kw}"
            problematic_substances.append(kw)

        # Deduplicate and sort
        unique_probs = sorted(list(set(problematic_substances)))
        
        # 3. Check for dosage warnings
        dosage_warning = any(kw in med_name.lower() for kw in DOSAGE_WARNING_KEYWORDS)
        if dosage_warning:
            reason += " (Warnung: Darreichungsform prüfen)"

        return AnalysisResult(
            product_name=med_name,
            category=category,
            reason=reason,
            problematic_substances=unique_probs,
            dosage_warning=dosage_warning,
            source=ingredient_data.source_url or "Unknown",
            raw_ingredients=ingredient_data.extracted_ingredients
        )

def extract_from_pdf(pdf_path: str) -> IngredientData:
    """
    Robustly extracts the ingredient section from a medication PDF.
    Uses priority-based regex matching for Fachinformation (FI) and Gebrauchsinformation (GI).
    """
    notes = []
    confidence = ConfidenceScore.LOW
    extracted_text = ""
    
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join([page.get_text() for page in doc])
        
        # Strategy A: Precise FI Section 6.1
        fi_pattern = re.compile(r"6\.1\s+Liste\s+der\s+sonstigen\s+Bestandteile(.*?)(?=6\.2)", re.S | re.I)
        match = fi_pattern.search(full_text)
        
        if match:
            extracted_text = match.group(1).strip()
            confidence = ConfidenceScore.HIGH
            notes.append("Successfully identified FI section 6.1")
        else:
            # Strategy B: Patient Leaflet (GI) "Was [Produkt] enthält"
            gi_pattern = re.compile(
                r"6\.\s+Inhalt\s+der\s+Packung.*?(?:Was.*?enth\u00e4lt|Die\s+sonstigen\s+Bestandteile\s+sind:)(.*?)"
                r"(?=Wie\s+.*?aussieht|Pharmazeutischer\s+Unternehmer|7\.\s+|8\.\s+)", 
                re.S | re.I
            )
            match = gi_pattern.search(full_text)
            
            if match:
                extracted_text = match.group(1).strip()
                confidence = ConfidenceScore.MEDIUM
                notes.append("Identified GI section 6 (Was enthält...)")
            else:
                # Strategy C: Greedy Fallback
                last_resort = re.compile(
                    r"sonstigen\s+Bestandteile\s+(?:sind|enthalten|:)(.*?)(?:\d\.|Wie\s+|Pharmazeutischer|$)", 
                    re.S | re.I
                )
                match = last_resort.search(full_text)
                if match:
                    extracted_text = match.group(1).strip()
                    confidence = ConfidenceScore.LOW
                    notes.append("Greedy extraction used")
                else:
                    extracted_text = "Bereich Hilfsstoffe nicht gefunden"
                    notes.append("No ingredient section detected")

    except Exception as e:
        logger.error(f"Failed to parse PDF {pdf_path}: {e}")
        extracted_text = f"Fehler beim Parsen: {e}"
        notes.append(f"Parsing error: {str(e)}")

    return IngredientData(
        raw_text=extracted_text,
        extracted_ingredients=extracted_text,
        confidence=confidence,
        extraction_notes=notes
    )
