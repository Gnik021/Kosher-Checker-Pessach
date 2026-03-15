import pandas as pd
import re
import os
import sys

sys.path.append(os.getcwd())
from med_crawler.utils import normalize_med_name

def clean_name_debug(name):
    if not name or str(name) == 'nan': return ""
    n = re.sub(r"\[.*?\]", "", str(name))
    n = re.sub(r"\(.*?\)", "", n)
    n = n.strip().lower()
    n = n.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    n = re.sub(r"[^a-z0-9+]", " ", n)
    return " ".join(n.split())

input_csv = 'Koscher_Medikamente_Pessach.csv'
df_orig = pd.read_csv(input_csv, sep=';')
orig_names = [str(m).strip() for m in df_orig['Medikament'].dropna()]

# Check "Sinupret" in original
print("--- SINUPRET IN ORIGINAL ---")
for n in orig_names:
    if "sinupret" in n.lower():
        print(f"Orig: '{n}' -> Clean: '{clean_name_debug(n)}'")

# Check "Sinupret" in results
print("\n--- SINUPRET IN POOL (V4) ---")
df_v4 = pd.read_excel('Pessach_Medikamente_POLISHED_V4.xlsx', sheet_name='Analyseergebnisse')
for n in df_v4['Produkt']:
    if "sinupret" in str(n).lower():
        print(f"Result: '{n}' -> Clean: '{clean_name_debug(n)}'")

# Analyze why the match might fail
print("\n--- MATCHING LOGIC SIMULATION ---")
example_orig = "Sinupret"
example_res = "[NEU] Sinupret Dragees"

co = clean_name_debug(example_orig)
cr = clean_name_debug(example_res)
print(f"Clean Orig: '{co}'")
print(f"Clean Res: '{cr}'")
print(f"Exact Match: {co == cr}")
print(f"Containment (co in cr): {co in cr}")
print(f"Words: O={set(co.split())}, R={set(cr.split())}")
print(f"Word Subset: {set(co.split()).issubset(set(cr.split()))}")
