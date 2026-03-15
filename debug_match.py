import pandas as pd
import re
import os
import sys

# Ensure local imports work
sys.path.append(os.getcwd())
from med_crawler.utils import normalize_med_name

input_csv = 'Koscher_Medikamente_Pessach.csv'
final_xlsx = 'Pessach_Medikamente_Premium_Final_v2.xlsx'

df_orig = pd.read_csv(input_csv, sep=';')
orig_names = [str(m).strip() for m in df_orig['Medikament'].dropna()]

df_final = pd.read_excel(final_xlsx, sheet_name='Analyseergebnisse')
final_names = [str(n) for n in df_final['Produkt']]

def clean(n):
    n = re.sub(r'\[.*?\]', '', n)
    n = re.sub(r'\(.*?\)', '', n)
    return n.strip().lower()

print(f"Total Original: {len(orig_names)}")
print(f"Total Processed: {len(final_names)}")

# Look for specific example: Aspirin
print("\n--- Aspirin Check ---")
for n in orig_names:
    if "aspirin" in n.lower():
        print(f"Original: '{n}' -> Base: '{normalize_med_name(n)[0]}'")
for n in final_names:
    if "aspirin" in n.lower():
        print(f"Final: '{n}' -> Base: '{normalize_med_name(n)[0]}'")

# Try a loose containment match
matches = 0
for oname in orig_names:
    obase = normalize_med_name(oname)[0] if normalize_med_name(oname) else clean(oname)
    found = False
    for fname in final_names:
        fbase = normalize_med_name(fname)[0] if normalize_med_name(fname) else clean(fname)
        if obase == fbase or obase in fbase or fbase in obase:
            found = True
            break
    if found:
        matches += 1

print(f"\nMatches with loose logic: {matches}")
