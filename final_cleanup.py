import pandas as pd
import os

def finalize_report():
    input_path = 'Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx'
    output_path = 'Koscher_Medikamente_Pessach_FINAL.xlsx'
    
    if not os.path.exists(input_path):
        # Fallback if V12 doesn't exist for some reason
        print(f"Error: {input_path} not found.")
        return

    # Load existing sheets
    xl = pd.ExcelFile(input_path)
    df_main = xl.parse('Analyseergebnisse')
    df_fresh = xl.parse('Fresh_Finds')
    df_missing = xl.parse('Suche_Ergebnislos')

    # --- 1. Filter out Durex and Dr Böhm ---
    def cleanup_filter(df, col_possible_names):
        target_col = None
        for col in col_possible_names:
            if col in df.columns:
                target_col = col
                break
        
        if target_col is None:
            return df
            
        # Case-insensitive filtering
        exclude_mask = df[target_col].str.contains('Durex|Dr Böhm|Dr. Böhm', case=False, na=False)
        return df[~exclude_mask]

    prod_cols = ['Produkt', 'Produkt (Fehlt)']
    df_final_main = cleanup_filter(df_main, prod_cols)
    df_final_fresh = cleanup_filter(df_fresh, prod_cols)
    df_final_missing = cleanup_filter(df_missing, prod_cols)

    # --- 2. Save and Format ---
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_final_main.to_excel(writer, sheet_name='Analyseergebnisse', index=False)
        df_final_fresh.to_excel(writer, sheet_name='Fresh_Finds', index=False)
        df_final_missing.to_excel(writer, sheet_name='Suche_Ergebnislos', index=False)

        workbook = writer.book
        
        # Formats
        fmt_ok = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_caution = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_not_ok = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white', 'border': 1, 'align': 'center'})

        # Column widths and Formatting
        for sheet_name, df_sheet in [('Analyseergebnisse', df_final_main), ('Fresh_Finds', df_final_fresh)]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_column('A:A', 40) # Produkt
            ws.set_column('B:B', 15) # Status
            ws.set_column('C:C', 30) # Probleme
            ws.set_column('D:D', 40) # Grund
            ws.set_column('E:E', 10) # Stufe
            ws.set_column('F:F', 50) # Quelle

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
            
            # Auto-Filter
            ws.autofilter(0, 0, last_row, 5)

        # Legend Sheet
        ws_legend = workbook.add_worksheet('Legende')
        ws_legend.write(0, 0, "Bedeutung der Status-Codes", fmt_header)
        ws_legend.write(1, 0, "OK", fmt_ok)
        ws_legend.write(1, 1, "Unbedenklich für Pessach (Stufe 2).")
        ws_legend.write(2, 0, "VORSICHT", fmt_caution)
        ws_legend.write(2, 1, "Enthält Kitniyot oder pot. problematische Stoffe (Stufe 1).")
        ws_legend.write(3, 0, "NICHT OK", fmt_not_ok)
        ws_legend.write(3, 1, "Enthält Chametz oder verbotene Stoffe wie Gelatine (Stufe 0).")
        ws_legend.set_column('A:A', 20)
        ws_legend.set_column('B:B', 60)

    print(f"Final Report created: {output_path}")

if __name__ == "__main__":
    finalize_report()
