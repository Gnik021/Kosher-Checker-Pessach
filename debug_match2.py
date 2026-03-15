import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
try:
    from med_crawler.utils import normalize_med_name
except ImportError:
    pass

input_csv = 'Koscher_Medikamente_Pessach.csv'
df_orig = pd.read_csv(input_csv, sep=';')
orig_names = [str(m).strip() for m in df_orig['Medikament'].dropna()]

df_res = pd.read_excel('Pessach_Medikamente_Premium_Final_v2.xlsx', sheet_name='Analyseergebnisse')
final_names = [str(n) for n in df_res['Produkt']]

def get_stripped(name):
    # normalize_med_name usually returns:
    # [0] clean base name
    # [1] suffix stripped
    # [2] brand (optional)
    import re
    n = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
    vars = normalize_med_name(n)
    if not vars: return n.lower()
    if len(vars) > 1:
        # Avoid returning just the brand if it's too generic
        # Wait, if vars = ['Aspirin', 'Aspirin'], len is 1.
        # If vars = ['Aspirin Direkt Granulat', 'Aspirin Direkt', 'Aspirin']
        # vars[1] is 'Aspirin Direkt'.
        return vars[1].lower()
    return vars[0].lower()

matches = 0
unmatched_finals = []
matched_origs = set()

for fn in final_names:
    f_strip = get_stripped(fn)
    found = False
    for on in orig_names:
        o_strip = get_stripped(on)
        
        # Match if exactly same stripped, or if one is fully contained in other and len > 5
        if f_strip == o_strip:
            found = True
        elif len(f_strip) > 5 and len(o_strip) > 5 and (f_strip in o_strip or o_strip in f_strip):
            # To avoid "Aspirin" matching "Aspirin Complex", check if words match
            f_words = set(f_strip.split())
            o_words = set(o_strip.split())
            if f_words.issubset(o_words) or o_words.issubset(f_words):
                found = True
                
        if found:
            matched_origs.add(on)
            break
            
    if found:
        matches += 1
    else:
        unmatched_finals.append(fn)

print(f"Total Finals: {len(final_names)}")
print(f"Total Matched: {matches}")
print(f"Total Unmatched Finals (will be [NEU]): {len(unmatched_finals)}")
print(f"Total Original: {len(orig_names)}")
print(f"Total Missing Originals: {len(orig_names) - len(matched_origs)}")

print("\nSample Unmatched Finals ([NEU]):")
for u in unmatched_finals[:10]: print(u)
