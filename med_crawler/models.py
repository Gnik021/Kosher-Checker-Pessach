from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class SuitabilityCategory(str, Enum):
    OK = "OK"
    NOT_KOSHER = "Nicht koscher"
    NOT_PESACH = "Nicht für Pessach"
    SUSPECTED_CHOMETZ = "Verdacht Chometz"
    ERROR = "API_ERROR"

class ConfidenceScore(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class IngredientData(BaseModel):
    raw_text: str
    extracted_ingredients: str = ""
    source_url: Optional[str] = None
    confidence: ConfidenceScore = ConfidenceScore.LOW
    extraction_notes: List[str] = []

class AnalysisResult(BaseModel):
    product_name: str
    category: SuitabilityCategory
    reason: str
    problematic_substances: List[str] = []
    dosage_warning: bool = False
    source: str
    raw_ingredients: str

class MedicationRecord(BaseModel):
    original_name: str
    clean_name: str
    basg_result: Optional[AnalysisResult] = None
    au_result: Optional[AnalysisResult] = None
    final_result: Optional[AnalysisResult] = None
