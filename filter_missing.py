import pandas as pd
import re
import os
import sys

# Ensure we can import from the current directory
sys.path.append(os.getcwd())
from med_crawler.utils import normalize_med_name

input_csv = r'C:\Users\bingu\Desktop\PESSACH PROJECT\Koscher_Medikamente_Pessach.csv'
final_path = r'C:\Users\bingu\Desktop\PESSACH PROJECT\Pessach_Medikamente_AT_Final.xlsx'
output_csv = r'C:\Users\bingu\Desktop\PESSACH PROJECT\recovery_input.csv'

def get_base_name(name):
    # Get the first variant (usually the cleaned brand/core name)
    variants = normalize_med_name(name)
    return variants[0] if variants else str(name).lower().strip()

# 1. Load final results and get normalized set of success
success_bases = set()
fail_bases = set()

if os.path.exists(final_path):
    df_final = pd.read_excel(final_path)
    for _, row in df_final.iterrows():
        prod = str(row['Produkt'])
        source = str(row.get('Quelle', '')).lower()
        reason = str(row.get('Grund für Einstufung', '')).lower()
        
        base = get_base_name(prod)
        
        if source == 'nan' or not source.strip() or 'nicht gefunden' in reason:
            fail_bases.add(base)
        else:
            success_bases.add(base)

# 2. Load input and compare
df_input = pd.read_csv(input_csv, sep=';')
retry_list = []

for _, row in df_input.iterrows():
    orig_name = str(row['Medikament'])
    if pd.isna(row['Medikament']): continue
    
    base = get_base_name(orig_name)
    
    # If the base name is not in our success set, or it's specifically in the fail set
    if base not in success_bases or base in fail_bases:
        retry_list.append(orig_name)

# Deduplicate
retry_list = sorted(list(set(retry_list)))

print(f"Total input: {len(df_input)}")
print(f"Successfully matched bases: {len(success_bases)}")
print(f"Targeting {len(retry_list)} medications for recovery.")

# Create the CSV for the orchestrator
pd.DataFrame({'Medikament': retry_list}).to_csv(output_csv, index=False, sep=';')
print(f"Saved to {output_csv}")
