import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
try:
    from med_crawler.utils import normalize_med_name, is_same_med
except ImportError:
    pass

input_csv = 'Koscher_Medikamente_Pessach.csv'
df_orig = pd.read_csv(input_csv, sep=';')
orig_names = [str(m).strip() for m in df_orig['Medikament'].dropna()]
orig_bases = [normalize_med_name(m)[0] for m in orig_names if normalize_med_name(m)]

df_res = pd.read_excel('Pessach_Medikamente_Premium_Final_v2.xlsx', sheet_name='Analyseergebnisse')
final_names = [str(n) for n in df_res['Produkt']]

print(f'Original count: {len(orig_names)}')
print(f'Final count: {len(final_names)}')
new_count = sum(1 for n in final_names if '[NEU]' in n)
print(f'Tagged as [NEU]: {new_count}')

print('\nOriginal Bases (First 10):', orig_bases[:10])
print('\nFinal Names (First 10):', final_names[:10])

df_miss = pd.read_excel('Pessach_Medikamente_Premium_Final_v2.xlsx', sheet_name='Fehlt')
missing_names = [str(n) for n in df_miss['Produkt (Fehlt)']]
print(f'\nMissing count: {len(missing_names)}')
