import re
from typing import List, Set

# Common pharmaceutical suffixes that can hinder direct API searches
PHARMA_SUFFIXES = [
    r"filmtablette\w*", r"brausetablette\w*", r"kapsel\w*", r"tablette\w*",
    r"granulat\w*", r"pulver\w*", r"beutel\w*", r"saft", r"lösung\w*",
    r"tropfen", r"suspension", r"sirup", r"creme", r"gel", r"salbe",
    r"nasenspray", r"augentropfen", r"inhalat\w*", r"zäpfchen",
    r"kautablette\w*", r"schmelztablette\w*", r"sticks?",
    r"retard\w*", r"fort\w*", r"akut", r"express", r"direkt",
    r"mg", r"g", r"ml", r"µg", r"mirkogramm",
    r"zum einnehmen", r"lösung zum", r"suspension zum", r"beutel zum", r"brause\w*"
]

def normalize_med_name(name: str) -> List[str]:
    """
    Generate an intelligent sequence of search variants for a medication name.
    1. Original name.
    2. Name with dosage form removed.
    3. Brand only (first word).
    """
    variants = []
    
    # 1. Cleaned original
    clean_original = name.strip()
    variants.append(clean_original)
    
    # 2. Strip suffixes
    stripped = clean_original.lower()
    for suffix in PHARMA_SUFFIXES:
        stripped = re.sub(rf"\b{suffix}\b", "", stripped, flags=re.I).strip()
    
    # Clean up double spaces or trailing punctuation
    stripped = re.sub(r"\s+", " ", stripped).strip()
    stripped = re.sub(r"[,;.-]+$", "", stripped).strip()
    
    if stripped and stripped.lower() != clean_original.lower():
        # Title case for better match possibility
        variants.append(stripped.title())
        
    # 3. Brand isolation (first word or two)
    words = clean_original.split()
    if words:
        brand = words[0]
        if brand.lower() not in [v.lower() for v in variants]:
            variants.append(brand)
            
    return variants

def is_same_med(name1: str, name2: str) -> bool:
    """Basic fuzzy/string check to see if two med names are likely the same."""
    def _simple_norm(n):
        return re.sub(r"[^a-z0-9]", "", n.lower())
    
    norm1 = _simple_norm(name1)
    norm2 = _simple_norm(name2)
    
    # Direct containment or equality
    return norm1 in norm2 or norm2 in norm1
