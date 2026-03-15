import pandas as pd
import json
import os

def load_recovery(json_path):
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []

def main():
    # Load Master Data
    master_path = 'Koscher_Medikamente_Pessach_FINAL_AUDIT.xlsx'
    xl = pd.ExcelFile(master_path)
    df_main = xl.parse('Analyseergebnisse')
    df_missing = xl.parse('Suche_Ergebnislos')
    
    # Load Recovery Data
    basg_rec = load_recovery('recovery_basg_v12.json')
    au_rec = load_recovery('recovery_au_v12.json')
    
    recovered_list = []
    
    for item in basg_rec + au_rec:
        res = item.get('result', {})
        # Map to EXACT schema: ['Produkt', 'Kategorie', 'Grund für Einstufung', 'Problematische Stoffe', 'Warnung', 'Quelle']
        record = {
            'Medikament (Original)': item.get('original_name'), # Helper for dedupe
            'Produkt': item.get('actual_name'),
            'Kategorie': res.get('category'),
            'Grund für Einstufung': res.get('sicherheitspuffer') or 'Analyse abgeschlossen',
            'Problematische Stoffe': res.get('problematische_stoffe') or 'Keine relevanten Stoffe gefunden',
            'Warnung': '',
            'Quelle': res.get('source_url') or ''
        }
        recovered_list.append(record)
        
    if not recovered_list:
        print("No recovered items found to merge.")
        return

    df_recovered = pd.DataFrame(recovered_list)
    
    # We want to merge based on 'Medikament (Original)' if it exists, or 'Produkt'
    # In df_main, we don't have 'Medikament (Original)' anymore? 
    # Let's check. If not, we use 'Produkt'.
    
    # Prepare for merge
    # We'll add 'Medikament (Original)' to df_main if it doesn't have it, as a copy of Produkt
    if 'Medikament (Original)' not in df_main.columns:
        df_main['Medikament (Original)'] = df_main['Produkt']
        
    df_final_main = pd.concat([df_main, df_recovered], ignore_index=True)
    
    # Deduplicate: Keep the latest record for each original request
    df_final_main = df_final_main.drop_duplicates(subset=['Medikament (Original)'], keep='last')
    
    # Remove the helper column for final export
    df_final_export = df_final_main.drop(columns=['Medikament (Original)'])
    
    # Ensure column order matches master
    columns_order = ['Produkt', 'Kategorie', 'Grund für Einstufung', 'Problematische Stoffe', 'Warnung', 'Quelle']
    df_final_export = df_final_export[columns_order]
    
    # Update missing list
    recovered_orig_names = [r['Medikament (Original)'] for r in recovered_list]
    df_final_missing = df_missing[~df_missing['Produkt (Fehlt)'].isin(recovered_orig_names)]
    
    # Export
    output_path = 'Koscher_Medikamente_Pessach_V11_COMPLETE.xlsx'
    
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_final_export.to_excel(writer, sheet_name='Analyseergebnisse', index=False)
        df_final_missing.to_excel(writer, sheet_name='Suche_Ergebnislos', index=False)
        
        # Legend (Copying logic from master)
        df_legend = pd.DataFrame({
            'Kategorie': ['OK', 'NICHT PESSACH TAUGLICH', 'NICHT KOSCHER', 'VERDACHT CHOMETZ'],
            'Bedeutung': [
                'Produkt ist für Pessach geeignet.',
                'Produkt ist NICHT für Pessach geeignet.',
                'Produkt ist generell nicht koscher.',
                'Pessach-Tauglichkeit fragwürdig (Chometz-Verdacht).'
            ]
        })
        df_legend.to_excel(writer, sheet_name='Legende_Hilfe', index=False)
        
        # Style
        workbook = writer.book
        worksheet = writer.sheets['Analyseergebnisse']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        ok_fmt = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        fail_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        warn_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
        
        for col_num, value in enumerate(df_final_export.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            
        for i, row_data in df_final_export.iterrows():
            row = i + 1
            kat = str(row_data['Kategorie'])
            if kat == 'OK':
                worksheet.set_row(row, None, ok_fmt)
            elif kat in ['NICHT PESSACH TAUGLICH', 'NICHT KOSCHER']:
                worksheet.set_row(row, None, fail_fmt)
            elif kat == 'VERDACHT CHOMETZ':
                worksheet.set_row(row, None, warn_fmt)

        worksheet.freeze_panes(1, 0)
        worksheet.set_column('A:A', 40)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 30)
        worksheet.set_column('D:D', 40)
        worksheet.set_column('F:F', 50)
        
    print(f"DONE! {len(recovered_list)} items merged. Output: {output_path}")

if __name__ == "__main__":
    main()
