import pandas as pd
import json
import os
import re
import glob

def normalize(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'ß', 'ss', text)
    text = re.sub(r'\d+\s*(mg|ml|ug|g|tabs|stück)', '', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return " ".join(text.split())

def is_same_product(name1, name2):
    n1 = normalize(name1)
    n2 = normalize(name2)
    if not n1 or not n2: return False
    
    # Check word sets (allow for extra words in finding)
    s1 = set(n1.split())
    s2 = set(n2.split())
    if not s1 or not s2: return False
    
    # If the first word doesn't match, it's probably not the same brand
    if n1.split()[0] != n2.split()[0]:
        return False
        
    # High overlap
    intersection = s1.intersection(s2)
    if len(intersection) >= min(len(s1), len(s2)) * 0.7:
        return True
        
    return False

def build_final_perfect():
    all_data = []

    # 1. Sweep JSONs
    for f in glob.glob('*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as jfile:
                items = json.load(jfile)
                if isinstance(items, list):
                    all_data.extend(items)
        except: pass

    # 2. Sweep XLSXs
    for f in glob.glob('*.xlsx'):
        if 'FINAL_PERFECT' in f: continue # Skip itself
        try:
            xl = pd.ExcelFile(f)
            for sheet in xl.sheet_names:
                df = xl.parse(sheet)
                if 'Produkt' in df.columns:
                    all_data.extend(df.to_dict('records'))
        except: pass

    # 3. Clean and Deduplicate Database
    db = {}
    for item in all_data:
        p = item.get('Produkt')
        if not p or not isinstance(p, str): continue
        if re.search(r'Durex|Böhm', p, re.I): continue
        
        norm = normalize(p)
        # Prefer items with analysis/source
        if norm not in db or (not db[norm].get('Quelle') and item.get('Quelle')):
            db[norm] = item

    # 4. Filter Target CSV
    df_csv = pd.read_csv('MEDIKAMENTE.csv', sep=';', encoding='utf-8', on_bad_lines='skip')
    csv_products = df_csv.iloc[:, 0].str.strip().tolist()

    tab_original = []
    tab_neu = []
    tab_missing = []
    
    used_db_keys = set()

    for csv_p in csv_products:
        if re.search(r'Durex|Böhm', csv_p, re.I): continue
        
        match = None
        for k, entry in db.items():
            if is_same_product(csv_p, entry['Produkt']):
                match = entry
                used_db_keys.add(k)
                break
        
        if match:
            ec = match.copy()
            ec['Produkt'] = csv_p # Keep original name
            tab_original.append(ec)
        else:
            tab_missing.append({"Produkt": csv_p})

    for k, entry in db.items():
        if k not in used_db_keys:
            tab_neu.append(entry)

    # 5. Final Polishing
    def finalize_list(items):
        clean = []
        for x in items:
            # Fix Quelle
            q = x.get('Quelle', '')
            if pd.isna(q): q = ""
            x['Quelle'] = q if str(q).startswith('http') else ""
            
            # Ensure Status is one of the 3
            st = str(x.get('Status', '')).upper()
            if 'NICHT OK' in st or 'NICHT P' in st: x['Status'] = 'NICHT OK'
            elif 'OK' in st or 'KP' in st: x['Status'] = 'OK'
            elif 'VORSICHT' in st or 'WARNUNG' in st: x['Status'] = 'VORSICHT'
            else: x['Status'] = 'OK' if not x.get('Status') else x['Status']
            
            clean.append(x)
        return clean

    tab_original = finalize_list(tab_original)
    tab_neu = finalize_list(tab_neu)

    # 6. Saving
    df_found = pd.DataFrame(tab_original)
    df_neu = pd.DataFrame(tab_neu)
    df_missing = pd.DataFrame(tab_missing)

    cols = ['Produkt', 'Status', 'Problematische Stoffe', 'Grund', 'Stufe', 'Quelle']
    df_found = df_found.reindex(columns=cols)
    df_neu = df_neu.reindex(columns=cols)

    output = 'Koscher_Medikamente_Pessach_DELIVERY_V15.xlsx'
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_found.to_excel(writer, sheet_name='Gefunden_Original', index=False)
        df_neu.to_excel(writer, sheet_name='Gefunden_NEU', index=False)
        df_missing.to_excel(writer, sheet_name='Vermisst_Original', index=False)

        workbook = writer.book
        # Formats
        fmt_ok = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'text_wrap': True})
        fmt_caution = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'text_wrap': True})
        fmt_not_ok = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'text_wrap': True})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white', 'border': 1, 'align': 'center'})

        for sn, df in [('Gefunden_Original', df_found), ('Gefunden_NEU', df_neu)]:
            ws = writer.sheets[sn]
            ws.freeze_panes(1, 0)
            ws.set_column('A:A', 45); ws.set_column('B:B', 15); ws.set_column('C:C', 30)
            ws.set_column('D:D', 45); ws.set_column('E:E', 10); ws.set_column('F:F', 60)
            lr = len(df)
            ws.conditional_format(1, 1, lr, 1, {'type': 'cell', 'criteria': '==', 'value': '"OK"', 'format': fmt_ok})
            ws.conditional_format(1, 1, lr, 1, {'type': 'cell', 'criteria': '==', 'value': '"VORSICHT"', 'format': fmt_caution})
            ws.conditional_format(1, 1, lr, 1, {'type': 'cell', 'criteria': '==', 'value': '"NICHT OK"', 'format': fmt_not_ok})
            ws.autofilter(0, 0, lr, 5)

        ws_m = writer.sheets['Vermisst_Original']
        ws_m.set_column('A:A', 50)
        
        # Legend
        ws_l = workbook.add_worksheet('Legende')
        ws_l.write(0, 0, "Pessach Status Legende", fmt_header)
        ws_l.write(1, 0, "OK", fmt_ok); ws_l.write(1, 1, "Unbedenklich (Stufe 2).")
        ws_l.write(2, 0, "VORSICHT", fmt_caution); ws_l.write(2, 1, "Kitniyot / Hilfsstoffe (Stufe 1).")
        ws_l.write(3, 0, "NICHT OK", fmt_not_ok); ws_l.write(3, 1, "Chametz / Gelatine (Stufe 0).")
        ws_l.set_column('A:A', 20); ws_l.set_column('B:B', 60)

    print(f"Final V15 Report created: {output}")

if __name__ == "__main__":
    build_final_perfect()
