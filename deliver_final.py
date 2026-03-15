import pandas as pd
import os
import re

def deliver_final_report():
    input_xlsx = 'Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx'
    input_csv = 'MEDIKAMENTE.csv'
    output_path = 'Koscher_Medikamente_Pessach_FINAL_DELIVERY.xlsx'
    
    if not os.path.exists(input_xlsx):
        print(f"Error: {input_xlsx} not found.")
        return

    # 1. Load Original Product List from CSV
    try:
        # Semicolon delimited based on probe
        df_csv = pd.read_csv(input_csv, sep=';', encoding='utf-8', on_bad_lines='skip')
        # Handle the case where the header is "Medikament;Status" but pandas splits it
        if 'Medikament' in df_csv.columns:
            original_names = set(df_csv['Medikament'].str.strip().str.lower().tolist())
        else:
            # Fallback if parsing didn't split correctly
            col = df_csv.columns[0]
            original_names = set(df_csv[col].str.split(';').str[0].str.strip().str.lower().tolist())
    except Exception as e:
        print(f"Warning: Could not parse {input_csv} perfectly: {e}")
        original_names = set()

    # 2. Load Consolidated Data
    xl = pd.ExcelFile(input_xlsx)
    # Combine results from previous sheets for re-sorting
    df_all_results = xl.parse('Analyseergebnisse')
    df_prev_missing = xl.parse('Suche_Ergebnislos')

    # --- Cleanup Utility ---
    def clean_output_df(df, is_missing=False):
        # Remove Durex and Dr Böhm
        mask = df.iloc[:, 0].str.contains('Durex|Dr Böhm|Dr. Böhm', case=False, na=False)
        df = df[~mask].copy()
        
        # Clean up links (remove local ones, keep https)
        if not is_missing and 'Quelle' in df.columns:
            def fix_link(link):
                if pd.isna(link): return ""
                link_str = str(link).strip()
                if link_str.startswith('http'):
                    return link_str
                return "" # Remove local file references like "1234.pdf"
            df['Quelle'] = df['Quelle'].apply(fix_link)
        
        return df

    # --- Filtering Logic ---
    # Separate Found items into "Original" and "NEU"
    df_found = clean_output_df(df_all_results)
    
    original_mask = df_found.iloc[:, 0].str.strip().str.lower().isin(original_names)
    df_tab_original = df_found[original_mask]
    df_tab_neu = df_found[~original_mask]

    # Clean up Missing list
    df_tab_missing = clean_output_df(df_prev_missing, is_missing=True)

    # --- 3. Save with Premium Formatting ---
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_tab_original.to_excel(writer, sheet_name='Medikamente_Original', index=False)
        df_tab_neu.to_excel(writer, sheet_name='NEU', index=False)
        df_tab_missing.to_excel(writer, sheet_name='Suche_Ergebnislos', index=False)

        workbook = writer.book
        
        # Formats
        fmt_ok = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'text_wrap': True})
        fmt_caution = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'text_wrap': True})
        fmt_not_ok = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'text_wrap': True})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white', 'border': 1, 'align': 'center'})

        for sheet_name, df_sheet in [('Medikamente_Original', df_tab_original), ('NEU', df_tab_neu)]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_column('A:A', 40) # Produkt
            ws.set_column('B:B', 15) # Status
            ws.set_column('C:C', 30) # Probleme
            ws.set_column('D:D', 45) # Grund
            ws.set_column('E:E', 10) # Stufe
            ws.set_column('F:F', 55) # Quelle

            last_row = len(df_sheet)
            ws.conditional_format(1, 1, last_row, 1, {
                'type': 'cell', 'criteria': '==', 'value': '"OK"', 'format': fmt_ok
            })
            ws.conditional_format(1, 1, last_row, 1, {
                'type': 'cell', 'criteria': '==', 'value': '"VORSICHT"', 'format': fmt_caution
            })
            ws.conditional_format(1, 1, last_row, 1, {
                'type': 'cell', 'criteria': '==', 'value': '"NICHT OK"', 'format': fmt_not_ok
            })
            ws.autofilter(0, 0, last_row, 5)

        # Missing sheet formatting
        ws_m = writer.sheets['Suche_Ergebnislos']
        ws_m.set_column('A:A', 50)
        ws_m.autofilter(0,0, len(df_tab_missing), 0)

        # Legend Sheet
        ws_legend = workbook.add_worksheet('Legende')
        ws_legend.write(0, 0, "Passover Status Bedeutung", fmt_header)
        ws_legend.write(1, 0, "OK", fmt_ok)
        ws_legend.write(1, 1, "Unbedenklich für Pessach (Stufe 2).")
        ws_legend.write(2, 0, "VORSICHT", fmt_caution)
        ws_legend.write(2, 1, "Enthält Kitniyot oder pot. kritische Hilfsstoffe (Stufe 1).")
        ws_legend.write(3, 0, "NICHT OK", fmt_not_ok)
        ws_legend.write(3, 1, "Enthält Chametz oder verbotene tierische Stoffe wie Gelatine (Stufe 0).")
        ws_legend.set_column('A:A', 20)
        ws_legend.set_column('B:B', 60)

    print(f"Final Delivery Report created: {output_path}")

if __name__ == "__main__":
    deliver_final_report()
