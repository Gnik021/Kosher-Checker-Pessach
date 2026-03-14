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
    """
    variants = []
    
    # 0. Strip technical tags first
    clean_original = re.sub(r"\[.*?\]", "", name)
    clean_original = re.sub(r"\(.*?\)", "", clean_original).strip()
    
    # 1. Base clean
    variants.append(clean_original)
    
    # 2. Strip suffixes
    stripped = clean_original.lower()
    for suffix in PHARMA_SUFFIXES:
        # Use word boundaries or end of string
        stripped = re.sub(rf"\b{suffix}\b", "", stripped, flags=re.I).strip()
        stripped = re.sub(rf"{suffix}$", "", stripped, flags=re.I).strip()

    # Special handling for + signs (e.g. Aspirin + C) - keep them but normalize space
    stripped = re.sub(r"\s*\+\s*", " + ", stripped)
    
    # Clean up double spaces or trailing punctuation
    stripped = re.sub(r"\s+", " ", stripped).strip()
    stripped = re.sub(r"[,;.-]+$", "", stripped).strip()
    
    if stripped and stripped.lower() != clean_original.lower():
        variants.append(stripped.title())
        
    # 3. Brand isolation (first word or two)
    words = stripped.split()
    if words:
        brand = words[0]
        if brand.lower() not in [v.lower() for v in variants]:
            variants.append(brand.title())
            
    # Remove duplicates while preserving order
    seen = set()
    unique_variants = []
    for v in variants:
        if v.lower() not in seen:
            unique_variants.append(v)
            seen.add(v.lower())
            
    return unique_variants

def is_same_med(name1: str, name2: str) -> bool:
    """Basic fuzzy/string check to see if two med names are likely the same."""
    def _simple_norm(n):
        return re.sub(r"[^a-z0-9]", "", n.lower())
    
    norm1 = _simple_norm(name1)
    norm2 = _simple_norm(name2)
    
    # Direct containment or equality
    return norm1 in norm2 or norm2 in norm1
