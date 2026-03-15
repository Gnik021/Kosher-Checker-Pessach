import pandas as pd
import os

def create_v12_report():
    input_path = 'Koscher_Medikamente_Pessach_V11_COMPLETE.xlsx'
    output_path = 'Koscher_Medikamente_Pessach_V12_COMPLETE.xlsx'
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Load existing sheets
    xl = pd.ExcelFile(input_path)
    df_main = xl.parse('Analyseergebnisse')
    df_missing = xl.parse('Suche_Ergebnislos')

    # --- 1. Recovery of Online Links for "Local" PDFs ---
    link_recovery = {
        "Algesal Cr me": "https://www.basg.gv.at/fileadmin/redakteure/01_Arzneimittel/Medikamentensuche/Gebrauchsinformation/Algesal_Creme.pdf",
        "Ambroxol Genericon L sliche Tabletten 60 Mg": "https://www.genericon.at/produkte/ambroxol-genericon-30-mg-tabletten/",
        "Aspirin Akut Brausetabletten": "https://www.apoverlag.at/produkt/aspirin-akut-500-mg-brausetablette/",
        "Azithromycin Genericon Filmtabletten": "https://www.genericon.at/produkte/azithromycin-genericon-500-mg-filmtabletten/",
        "Bronchipret Saft": "https://www.bionorica.de/patienten/produkte/bronchipret-saft-te/",
        "Buscopan Z pfchen 10 Mg": "https://www.apoverlag.at/produkt/buscopan-10-mg-zaepfchen/",
        "Cetirizin Ratiopharm Filmtabletten": "https://www.ratiopharm.de/produkte/details/pzn-0419131.html",
        "Cetirizin Sandoz Filmtabletten": "https://www.sandoz.at/produkte/cetirizin-sandoz-10-mg-filmtabletten/",
        "Chlorhexamed Forte  Alle Varianten Von Forte": "https://www.chlorhexamed.de/produkte/chlorhexamed-forte-alkoholfrei-0-2-prozent-loesung/",
        "Prospan Saft": "https://www.prospan.de/produkte/prospan-hustensaft/"
    }

    def update_quelle(row):
        prod = row['Produkt']
        if prod in link_recovery:
            return link_recovery[prod]
        return row['Quelle']

    df_main['Quelle'] = df_main.apply(update_quelle, axis=1)

    # --- 2. Create "Fresh Finds" Data ---
    fresh_finds_data = [
        {"Produkt": "Acerola Vitamin C Drink", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Rein pflanzlich (Acerola), keine Gelatine/Stärke.", "Stufe": 2, "Quelle": "https://www.verumingredients.com/acerola-pure-powder/"},
        {"Produkt": "Ascorbin Säure Vitamin C Pulver", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "100% reine Ascorbinsäure, Pesach-tauglich (Nishtana).", "Stufe": 2, "Quelle": "https://oukosher.org/passover/guidelines/medicine-guidelines/"},
        {"Produkt": "Aspirin + C Forte Brausetabletten", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Enthält Natriumhydrogencarbonat, Citronensäure, Povidone. Keine Stärke.", "Stufe": 2, "Quelle": "https://www.shop-apotheke.at/arzneimittel/10006325/aspirin-c-forte-800-mg-480-mg.htm"},
        {"Produkt": "Baby-Luuf Und Kinder-Luuf Balsam", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Ätherische Öle in Vaseline/Paraffin. Frei von Menthol/Stärke.", "Stufe": 2, "Quelle": "https://www.luuf.at/produkte/baby-luuf-balsam/"},
        {"Produkt": "Bittersalz", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Reines Magnesiumsulfat, mineralisch, Pesach-tauglich.", "Stufe": 2, "Quelle": "https://www.apotheken-umschau.de/medikamente/beipackzettel/bittersalz-magnesiumsulfat-100-g-102143.html"},
        {"Produkt": "Blistex Lippenpflege", "Status": "VORSICHT", "Problematische Stoffe": "Collagen (tierisch)", "Grund": "Enthält Isostearoyl Hydrolyzed Collagen (pot. nicht koscher).", "Stufe": 1, "Quelle": "https://incidecoder.com/products/blistex-daily-lip-care-spf15"},
        {"Produkt": "Boswellia Loges Weihrauch Kapseln", "Status": "NICHT OK", "Problematische Stoffe": "Gelatine (Rind)", "Grund": "Kapselhülle besteht aus Rindergelatine.", "Stufe": 0, "Quelle": "https://www.loges.de/produkte/boswellia-loges/"},
        {"Produkt": "Brusttee (Species Pectorales)", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Reine Kräutermischung (Eibisch, Süßholz, Anis). Kein Chametz.", "Stufe": 2, "Quelle": "https://www.basg.gv.at/fileadmin/redakteure/01_Arzneimittel/Medikamentensuche/Gebrauchsinformation/Brusttee.pdf"},
        {"Produkt": "Coldamaris Akut Nasenspray", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Algenextrakt (Carragelose) in Salzlösung. Frei von Stärke/Gelatine.", "Stufe": 2, "Quelle": "https://www.coldamaris.at/produkte/coldamaris-akut/"},
        {"Produkt": "Dentinox Gel", "Status": "VORSICHT", "Problematische Stoffe": "Ethanol, Caramel", "Grund": "Enthält Ethanol (pot. Getreide) und Caramel (pot. Weizen-Glukose).", "Stufe": 1, "Quelle": "https://www.dentinox.de/produkte/dentinox-gel-n/"},
        {"Produkt": "Dr Böhm Ein- Und Durchschlaf", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Pflanzliche Extrakte (Baldrian, Melisse). Frei von Gelatine.", "Stufe": 2, "Quelle": "https://www.drboehm.at/produkte/ein-und-durchschlaf/"},
        {"Produkt": "Dorithricin Halstabletten", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Frei von tierischen Inhaltsstoffen und Stärke.", "Stufe": 2, "Quelle": "https://www.dorithricin.de/produkte/dorithricin-classic/"},
        {"Produkt": "Enterobene", "Status": "VORSICHT", "Problematische Stoffe": "Maisstärke (Kitniyot)", "Grund": "Enthält Maisstärke. Für Aschkenasim pot. problematisch (Kitniyot).", "Stufe": 1, "Quelle": "https://www.ratiopharm.at/produkte/details/pzn-436329.html"},
        {"Produkt": "Fenistil Tropfen", "Status": "VORSICHT", "Problematische Stoffe": "Ethanol (6.3%)", "Grund": "Enthält Ethanol. Herkunft nicht spezifiziert (pot. Chametz).", "Stufe": 1, "Quelle": "https://www.fenistil.de/produkte/fenistil-tropfen/"},
        {"Produkt": "Faktu Clean Tücher", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Pflanzenfasern mit Ruscus-Extrakt. Keine kritischen Stoffe.", "Stufe": 2, "Quelle": "https://www.faktu.de/produkte/faktu-clean/"},
        {"Produkt": "Easydrop Augentropfen", "Status": "OK", "Problematische Stoffe": "Keine relevanten Stoffe gefunden", "Grund": "Hyaluronsäure in steriler Kochsalzlösung.", "Stufe": 2, "Quelle": "https://www.easydrop.at/produkte/hyaluron-liquid/"}
    ]
    df_fresh = pd.DataFrame(fresh_finds_data)

    # Reorder columns to match main sheet
    cols = df_main.columns.tolist()
    df_fresh = df_fresh.reindex(columns=cols)

    # Add Fresh Finds to the main report if they were missing
    # (Just to make sure they are in the primary list too)
    df_final_main = pd.concat([df_main, df_fresh], ignore_index=True).drop_duplicates(subset=['Produkt'])

    # --- 3. Save and Format ---
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_final_main.to_excel(writer, sheet_name='Analyseergebnisse', index=False)
        df_fresh.to_excel(writer, sheet_name='Fresh_Finds', index=False)
        df_missing.to_excel(writer, sheet_name='Suche_Ergebnislos', index=False)

        workbook = writer.book
        
        # Formats
        fmt_ok = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_caution = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_not_ok = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'text_wrap': True, 'align': 'vcenter'})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white', 'border': 1, 'align': 'center'})

        # Legends and Formatting
        for sheet_name in ['Analyseergebnisse', 'Fresh_Finds']:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_column('A:A', 40) # Produkt
            ws.set_column('B:B', 15) # Status
            ws.set_column('C:C', 30) # Probleme
            ws.set_column('D:D', 40) # Grund
            ws.set_column('E:E', 10) # Stufe
            ws.set_column('F:F', 50) # Quelle

            # Apply conditional formatting based on Status column (B)
            last_row = len(df_final_main if sheet_name == 'Analyseergebnisse' else df_fresh)
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

    print(f"V12 Report created: {output_path}")

if __name__ == "__main__":
    create_v12_report()
