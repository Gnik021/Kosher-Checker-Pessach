import pandas as pd
import json
import os
import re

def normalize(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    # Normalize special characters
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'ß', 'ss', text)
    # Remove dosage and generic terms
    text = re.sub(r'\d+\s*(mg|ml|ug|g|tabs|stück)', '', text)
    # Remove non-alphanumeric except space
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return " ".join(text.split())

def is_same_product(name1, name2):
    n1 = normalize(name1)
    n2 = normalize(name2)
    if not n1 or not n2: return False
    
    # Prefix match (first 2 words)
    w1 = n1.split()[:2]
    w2 = n2.split()[:2]
    if len(w1) >= 2 and len(w2) >= 2 and w1 == w2:
        return True
    
    # Fallback: if one is a subset of the other (first word must match)
    if n1.split()[0] == n2.split()[0]:
        if n1 in n2 or n2 in n1:
            return True
            
    return False

def build_final_delivery():
    # 1. Gather all verification results
    all_results = []
    
    # From JSONs
    for json_path in ['recovery_basg_v12.json', 'recovery_au_v12.json']:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try: 
                    data = json.load(f)
                    all_results.extend(data)
                except: pass

    # From XLSX (the most recent complete one)
    if os.path.exists('Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx'):
        xl = pd.ExcelFile('Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx')
        for sheet in ['Analyseergebnisse', 'Fresh_Finds']:
            if sheet in xl.sheet_names:
                all_results.extend(xl.parse(sheet).to_dict('records'))

    # Deduplicate by normalized name
    final_db = {}
    for res in all_results:
        prod = res.get('Produkt')
        if not prod: continue
        norm = normalize(prod)
        # Avoid Durex/Böhm
        if re.search(r'Durex|Böhm', prod, re.I): continue
        
        # Keep the most complete one (the one with Analysis/Quelle)
        if norm not in final_db or (not final_db[norm].get('Quelle') and res.get('Quelle')):
            final_db[norm] = res

    # 2. Extract Original List (310 items)
    df_csv = pd.read_csv('MEDIKAMENTE.csv', sep=';', encoding='utf-8', on_bad_lines='skip')
    csv_products = df_csv.iloc[:, 0].str.strip().tolist()

    # 3. Create the 3 Tabs
    found_original = []
    neu_items = []
    missing_original = []
    
    used_norm_keys = set()
    mapped_csv_indices = set()

    for i, csv_prod in enumerate(csv_products):
        # Avoid Durex/Böhm in original too (if user asked to remove them)
        if re.search(r'Durex|Böhm', csv_prod, re.I): continue
        
        best_match = None
        for norm_key, res in final_db.items():
            if is_same_product(csv_prod, res['Produkt']):
                best_match = res
                used_norm_keys.add(norm_key)
                break
        
        if best_match:
            # Map back to CSV name
            res_copy = best_match.copy()
            res_copy['Produkt'] = csv_prod # Keep original name as requested
            found_original.append(res_copy)
            mapped_csv_indices.add(i)
        else:
            missing_original.append({"Produkt": csv_prod})

    # Fresh finds / NEU items
    for norm_key, res in final_db.items():
        if norm_key not in used_norm_keys:
            neu_items.append(res)

    # 4. Final Cleanup of Links
    def cleanup_links(items):
        for item in items:
            link = item.get('Quelle', '')
            if pd.isna(link): link = ""
            if isinstance(link, str) and link.startswith('http'):
                item['Quelle'] = link
            else:
                item['Quelle'] = ""
        return items

    found_original = cleanup_links(found_original)
    neu_items = cleanup_links(neu_items)

    # 5. Export to Excel
    df_found = pd.DataFrame(found_original)
    df_neu = pd.DataFrame(neu_items)
    df_missing = pd.DataFrame(missing_original)

    # Reorder columns for found tabs
    cols = ['Produkt', 'Status', 'Problematische Stoffe', 'Grund', 'Stufe', 'Quelle']
    df_found = df_found.reindex(columns=cols)
    df_neu = df_neu.reindex(columns=cols)

    output_path = 'Koscher_Medikamente_Pessach_FINAL_FINAL.xlsx'
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_found.to_excel(writer, sheet_name='Medikamente_Gefunden', index=False)
        df_neu.to_excel(writer, sheet_name='NEU', index=False)
        df_missing.to_excel(writer, sheet_name='Medikamente_Vermisst', index=False)

        workbook = writer.book
        # Formats
        fmt_ok = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'text_wrap': True})
        fmt_caution = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'text_wrap': True})
        fmt_not_ok = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'text_wrap': True})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white', 'border': 1, 'align': 'center'})

        for sheet_name, df_sheet in [('Medikamente_Gefunden', df_found), ('NEU', df_neu)]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_column('A:A', 45)
            ws.set_column('B:B', 15)
            ws.set_column('C:C', 35)
            ws.set_column('D:D', 45)
            ws.set_column('E:E', 10)
            ws.set_column('F:F', 60)
            
            last_row = len(df_sheet)
            ws.conditional_format(1, 1, last_row, 1, {'type': 'cell', 'criteria': '==', 'value': '"OK"', 'format': fmt_ok})
            ws.conditional_format(1, 1, last_row, 1, {'type': 'cell', 'criteria': '==', 'value': '"VORSICHT"', 'format': fmt_caution})
            ws.conditional_format(1, 1, last_row, 1, {'type': 'cell', 'criteria': '==', 'value': '"NICHT OK"', 'format': fmt_not_ok})
            ws.autofilter(0, 0, last_row, 5)

        # Missing sheet
        ws_m = writer.sheets['Medikamente_Vermisst']
        ws_m.set_column('A:A', 50)

        # Legend Sheet
        ws_legend = workbook.add_worksheet('Legende')
        ws_legend.write(0, 0, "Pessach Status Legende", fmt_header)
        ws_legend.write(1, 0, "OK", fmt_ok)
        ws_legend.write(1, 1, "Unbedenklich für Pessach (Stufe 2).")
        ws_legend.write(2, 0, "VORSICHT", fmt_caution)
        ws_legend.write(2, 1, "Enthält Kitniyot oder pot. problematische Stoffe (Stufe 1).")
        ws_legend.write(3, 0, "NICHT OK", fmt_not_ok)
        ws_legend.write(3, 1, "Enthält Chametz oder verbotene Stoffe (z.B. tierische Gelatine) (Stufe 0).")
        ws_legend.set_column('A:A', 20)
        ws_legend.set_column('B:B', 70)

    print(f"Final Final Report created: {output_path}")

if __name__ == "__main__":
    build_final_delivery()
