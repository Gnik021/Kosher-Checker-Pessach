import pandas as pd
import os
import re

def normalize(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    # Remove accents/special chars
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'ß', 'ss', text)
    # Remove dosage and generic terms
    text = re.sub(r'\d+\s*(mg|ml|ug|g|tabs|stück)', '', text)
    # Remove non-alphanumeric except space
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Collapse spaces
    text = " ".join(text.split())
    return text

def audit_mapping():
    # 1. Load CSV
    df_csv = pd.read_csv('MEDIKAMENTE.csv', sep=';', encoding='utf-8', on_bad_lines='skip')
    csv_products = df_csv.iloc[:, 0].tolist()
    
    # 2. Load Found
    xl = pd.ExcelFile('Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx')
    df_found = xl.parse('Analyseergebnisse')
    df_fresh = xl.parse('Fresh_Finds')
    all_found = pd.concat([df_found, df_fresh], ignore_index=True)
    found_products = all_found['Produkt'].tolist()
    
    # Normalize sets
    norm_found = {normalize(p): p for p in found_products}
    
    matches = []
    missing = []
    
    for p in csv_products:
        p_norm = normalize(p)
        if not p_norm: continue
        
        # Exact match
        if p_norm in norm_found:
            matches.append((p, norm_found[p_norm]))
        else:
            # Fuzzy match attempt (first 2 words)
            p_words = p_norm.split()[:2]
            if len(p_words) >= 1:
                prefix = " ".join(p_words)
                found_match = False
                for nf_key, nf_val in norm_found.items():
                    if nf_key.startswith(prefix):
                        matches.append((p, nf_val))
                        found_match = True
                        break
                if not found_match:
                    missing.append(p)
            else:
                missing.append(p)

    print(f"Total CSV Items: {len(csv_products)}")
    print(f"Found Matches: {len(matches)}")
    print(f"Missing: {len(missing)}")
    
    print("\nSample Matches (CSV -> Found):")
    for m in matches[:10]:
        print(f"  {m[0]} -> {m[1]}")
        
    print("\nSample Missing:")
    for ms in missing[:10]:
        print(f"  {ms}")

if __name__ == "__main__":
    audit_mapping()
