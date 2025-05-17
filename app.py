import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from fpdf import FPDF # Für PDF-Export
import io # Für Bild-Bytes im PDF-Export
import os # Für das Verwalten von Projektdateien

# --- Standardwerte und Annahmen ---
# (Die meisten Konstanten bleiben gleich wie im vorherigen Code)
HEIZGRENZE_TEMP = 15.0
RAUMTEMPERATUR_SOLL = 20.0
U_WERTE_BAUJAHR_TYPISCH = {
    "Vor 1918": {"Außenwand": 1.7, "Dach": 1.5, "Bodenplatte": 1.2, "Fenster": 4.0},
    "1919-1948": {"Außenwand": 1.6, "Dach": 1.4, "Bodenplatte": 1.0, "Fenster": 3.5},
    "1949-1977": {"Außenwand": 1.4, "Dach": 1.0, "Bodenplatte": 0.8, "Fenster": 2.8},
    "1978-1983 (WSchV 77)": {"Außenwand": 0.9, "Dach": 0.5, "Bodenplatte": 0.6, "Fenster": 2.6},
    "1984-1994 (WSchV 84)": {"Außenwand": 0.6, "Dach": 0.4, "Bodenplatte": 0.5, "Fenster": 2.2},
    "1995-2001 (WSchV 95)": {"Außenwand": 0.45, "Dach": 0.3, "Bodenplatte": 0.4, "Fenster": 1.8},
    "2002-2008 (EnEV 2002)": {"Außenwand": 0.35, "Dach": 0.25, "Bodenplatte": 0.35, "Fenster": 1.5},
    "2009-2013 (EnEV 2009)": {"Außenwand": 0.28, "Dach": 0.20, "Bodenplatte": 0.30, "Fenster": 1.3},
    "2014-2020 (EnEV 2014/2016)": {"Außenwand": 0.24, "Dach": 0.20, "Bodenplatte": 0.28, "Fenster": 1.1},
    "GEG 2020/2023 Neubau Standard": {"Außenwand": 0.20, "Dach": 0.14, "Bodenplatte": 0.25, "Fenster": 0.95},
}
FENSTER_U_WERTE_BAUJAHR = {
    "Vor 1978 (Einfachglas)": 5.2,
    "1978-1994 (Isolierglas)": 2.8,
    "1995-2003 (WS-Glas)": 1.7,
    "2004-2010 (Optimiertes WS-Glas)": 1.3,
    "Nach 2010 (3-fach Verglasung)": 0.9,
}
temp_data_tuples = [
    ("Jan", 1.5, -1.0, 4.0, 31), ("Feb", 2.0, -0.5, 4.5, 28), ("Mär", 5.0, 2.0, 8.0, 31),
    ("Apr", 9.0, 5.0, 13.0, 30), ("Mai", 13.5, 8.0, 18.0, 31), ("Jun", 16.5, 11.0, 21.0, 30),
    ("Jul", 18.5, 13.0, 23.0, 31), ("Aug", 18.0, 12.5, 22.5, 31), ("Sep", 14.0, 9.0, 19.0, 30),
    ("Okt", 9.5, 5.5, 13.5, 31), ("Nov", 5.0, 2.0, 8.0, 30), ("Dez", 2.5, -0.5, 4.5, 31)
]
REFERENCE_TEMP_PROFILE = pd.DataFrame(temp_data_tuples, columns=["Monat", "Mitteltemperatur", "Min-Temperatur", "Max-Temperatur", "TageImMonat"])
REFERENCE_TEMP_PROFILE["MonatNr"] = range(1, 13)

PV_ERTRAG_PROFIL_RELATIV = {
    1: 0.025, 2: 0.045, 3: 0.08, 4: 0.11, 5: 0.13, 6: 0.14,
    7: 0.13, 8: 0.12, 9: 0.09, 10: 0.06, 11: 0.035, 12: 0.025
}
pv_daily_shape = np.array([0,0,0,0,0,0,0.05,0.2,0.4,0.6,0.8,0.95,1,0.95,0.8,0.6,0.4,0.2,0.05,0,0,0,0,0])
hh_daily_shape = np.array([0.03,0.025,0.02,0.02,0.025,0.035,0.045,0.05,0.045,0.04,0.038,0.038,0.04,0.04,0.042,0.045,0.05,0.06,0.06,0.055,0.05,0.04,0.035,0.032])
hh_daily_shape = hh_daily_shape / hh_daily_shape.sum()
dhw_daily_shape = np.array([0.03,0.02,0.02,0.02,0.03,0.05,0.07,0.06,0.04,0.03,0.03,0.03,0.03,0.03,0.04,0.05,0.06,0.08,0.07,0.06,0.05,0.04,0.03,0.02])
dhw_daily_shape = dhw_daily_shape / dhw_daily_shape.sum()
heating_daily_shape = np.array([0.035,0.03,0.025,0.025,0.03,0.04,0.05,0.05,0.045,0.04,0.04,0.04,0.04,0.04,0.045,0.045,0.05,0.05,0.05,0.045,0.04,0.035,0.035,0.035])
heating_daily_shape = heating_daily_shape / heating_daily_shape.sum()

# --- HILFSFUNKTIONEN ---
def get_u_wert_vorschlag(baujahr_str, komponente):
    return U_WERTE_BAUJAHR_TYPISCH.get(baujahr_str, {}).get(komponente, 0.0)

def get_fenster_u_wert_vorschlag(fenster_baujahr_str):
    return FENSTER_U_WERTE_BAUJAHR.get(fenster_baujahr_str, 1.3)

# --- PDF Export Klasse ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Energiebedarfsanalyse Mehrfamilienhaus', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def chapter_body(self, body_dict):
        self.set_font('Arial', '', 10)
        for key, value in body_dict.items():
            self.multi_cell(0, 7, f"{key}: {value}")
        self.ln()

    def add_plotly_fig(self, fig, title="Plot"):
        try:
            img_bytes = fig.to_image(format="png", scale=2, engine="kaleido") # Benötigt kaleido
            img_file = io.BytesIO(img_bytes)
            
            # Dynamische Bildgröße basierend auf Seitenbreite
            page_width = self.w - 2 * self.l_margin
            img_width = page_width * 0.9 # 90% der Seitenbreite
            
            # Bild einfügen (FPDF erkennt das Format aus den Bytes)
            self.image(img_file, w=img_width, type='PNG')
            self.ln(5)
        except Exception as e:
            self.set_font('Arial', 'I', 8)
            self.multi_cell(0, 5, f"(Fehler beim Rendern der Grafik '{title}': {e}. Kaleido installiert?)")
            self.ln(5)


# --- Initialisierung Session State ---
default_werte = {
    # Globale Einstellungen
    "user_name": "Standardbenutzer", "project_name": "MeinProjekt",
    "anzahl_personen": 10, "energiesparfaktor_allgemein": 0.1,
    "strompreis": 0.30, "gaspreis": 0.10, "fernwaermepreis": 0.12, "einspeiseverguetung": 0.08,
    "prognose_jahre": 15, "preissteigerung_strom": 3.0, "preissteigerung_gas": 4.0, "preissteigerung_fernwaerme": 3.5,
    # Gebäudeparameter
    "baujahr_haus_str": list(U_WERTE_BAUJAHR_TYPISCH.keys())[-3], "keller_option": "Unterkellert",
    "flaeche_aussenwand_gesamt": 300.0, "aussenwand_gedaemmt_anteil": 1.0, "u_aussenwand_gedaemmt": 0.0, "u_aussenwand_ungedaemmt": 0.0,
    "daemmstandard_wand": "Baujahrstandard",
    "flaeche_dach": 150.0, "flaeche_boden": 150.0, "flaeche_fenster_gesamt": 40.0,
    "fenster_baujahr_str": list(FENSTER_U_WERTE_BAUJAHR.keys())[-1],
    "u_dach": 0.0, "u_boden": 0.0, "u_fenster": 0.0, # Werden initialisiert
    # Haushaltsstrom
    "haushaltstrom_manuell_kWh": 0.0,
    # PV-Parameter
    "use_pv": True, "pv_kwp": 10.0, "spez_jahresertrag_pv": 950,
    "pv_ausrichtung": "Süd", "pv_neigung": 35, "use_speicher": True, "speicher_kwh": 10.0,
    "pv_nutzungs_strategie": "Eigenverbrauch priorisieren (Haushalt > WP > Speicher > Netz)",
    "invest_adj_pv": 0.0,
    # Heizsysteme
    "vorhandenes_heizsystem": "Keines",
    "invest_adj_gas": 0.0, "invest_adj_wp": 0.0, "invest_adj_fw": 0.0
}
# U-Werte initial basierend auf Baujahr setzen (für u_aussenwand_gedaemmt/ungedaemmt)
default_werte["u_aussenwand_gedaemmt"] = get_u_wert_vorschlag(default_werte["baujahr_haus_str"], "Außenwand")
default_werte["u_aussenwand_ungedaemmt"] = get_u_wert_vorschlag(default_werte["baujahr_haus_str"], "Außenwand") # Gleicher Wert initial
default_werte["u_dach"] = get_u_wert_vorschlag(default_werte["baujahr_haus_str"], "Dach")
default_werte["u_boden"] = get_u_wert_vorschlag(default_werte["baujahr_haus_str"], "Bodenplatte")
default_werte["u_fenster"] = get_fenster_u_wert_vorschlag(default_werte["fenster_baujahr_str"])

for key, value in default_werte.items():
    if key not in st.session_state:
        st.session_state[key] = value
# --- Ende Initialisierung Session State ---

# --- STREAMLIT APP ---
st.set_page_config(layout="wide", page_title="Energiebedarfsanalyse MFH")
st.title("Kostenanalyse Energiebedarf Mehrfamilienhaus")

# Projekt Ordner erstellen, falls nicht vorhanden
PROJECTS_DIR = "energie_projekte"
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

# --- 0. PROJEKTVERWALTUNG (VEREINFACHT) ---
with st.sidebar.expander("Projekt Speichern & Laden", expanded=False):
    st.text_input("Benutzer/Team-Kürzel (für Dateiname)", value=st.session_state.user_name, key="user_name")
    st.text_input("Projektname (für Dateiname)", value=st.session_state.project_name, key="project_name")
    
    file_basename = f"{st.session_state.user_name}_{st.session_state.project_name}.json"
    file_path = os.path.join(PROJECTS_DIR, file_basename)

    if st.button("Projekt Speichern"):
        try:
            # Manuell alle relevanten session_state keys sammeln
            params_to_save = {k: st.session_state[k] for k in default_werte.keys() if k in st.session_state}
            # Füge dynamisch generierte Keys hinzu, falls nötig (z.B. u_aussenwand)
            # Dies ist eine Vereinfachung; eine robustere Methode wäre, alle Keys beim Widget-Erstellen zu erfassen
            for u_key in ["u_aussenwand_gedaemmt", "u_aussenwand_ungedaemmt", "u_dach", "u_boden", "u_fenster"]:
                 if u_key in st.session_state: params_to_save[u_key] = st.session_state[u_key]


            with open(file_path, 'w') as f:
                json.dump(params_to_save, f, indent=2)
            st.success(f"Projekt '{file_basename}' erfolgreich gespeichert!")
        except Exception as e:
            st.error(f"Fehler beim Speichern: {e}")

    # Laden: Liste existierender Projektdateien oder Upload
    # Vereinfachung: Nur Upload
    uploaded_file = st.file_uploader("Projekt Laden (.json)", type="json", key="project_upload")
    if uploaded_file is not None:
        try:
            loaded_data = json.load(uploaded_file)
            for key, value in loaded_data.items(): # Parameter in session_state laden
                st.session_state[key] = value
            # Extra Logik um sicherzustellen, dass alle default_werte Keys im session_state sind, falls Datei alt
            for default_key, default_val in default_werte.items():
                if default_key not in st.session_state:
                    st.session_state[default_key] = default_val
            
            st.success(f"Projekt '{uploaded_file.name}' geladen! Bitte Seite ggf. neu laden (F5) oder warten bis Widgets aktualisiert sind.")
            # st.experimental_rerun() # Löst automatischen Rerun aus
        except Exception as e:
            st.error(f"Fehler beim Laden der Datei: {e}")


# --- 1. GLOBALE EINSTELLUNGEN (KOMPAKT) ---
with st.sidebar.expander("Globale Einstellungen", expanded=True):
    st.number_input("Anzahl Personen im Haus", min_value=1, key="anzahl_personen")
    col_esf1, col_esf2 = st.columns([3,1])
    with col_esf1:
        st.slider("Allgemeiner Energiespar-Faktor", 0.0, 1.0, key="energiesparfaktor_allgemein",
                  help="0=Standardverbrauch, 1=Maximal sparsam. Beeinflusst Haushaltsstrom und Brauchwasser.")
    with col_esf2:
        with st.popover("Info"):
            st.markdown("""
            Der Energiespar-Faktor reduziert:
            - **Brauchwasserbedarf:** Reduktion um `Faktor * 50%`. Ein Faktor von 0.2 bedeutet 10% weniger Brauchwasserenergie.
            - **Haushaltsstrombedarf:** Direkte Reduktion um `Faktor * 100%`. Ein Faktor von 0.2 bedeutet 20% weniger Haushaltsstrom.
            """)

    st.subheader("Energiepreise (€/kWh)")
    st.number_input("Strompreis (€/kWh)", format="%.3f", key="strompreis")
    st.number_input("Gaspreis (€/kWh)", format="%.3f", key="gaspreis")
    st.number_input("Fernwärmepreis (€/kWh)", format="%.3f", key="fernwaermepreis")
    st.number_input("Einspeisevergütung PV (€/kWh)", format="%.3f", key="einspeiseverguetung")

    st.subheader("Prognose")
    st.slider("Betrachtungszeitraum Prognose (Jahre)", 5, 30, key="prognose_jahre")
    st.slider("Jährl. Preissteigerung Strom (%)", 0.0, 10.0, key="preissteigerung_strom", step=0.1)
    st.slider("Jährl. Preissteigerung Gas (%)", 0.0, 10.0, key="preissteigerung_gas", step=0.1)
    st.slider("Jährl. Preissteigerung Fernwärme (%)", 0.0, 10.0, key="preissteigerung_fernwaerme", step=0.1)


# --- HAUPTBEREICH ---
tab1, tab2, tab3, tab4 = st.tabs(["Gebäude & Bedarf", "PV & Weitere Verbräuche", "Systemvergleich & Kosten", "Tagesprofil & Export"])

with tab1: # Gebäude & Bedarf
    with st.expander("1. Gebäudeparameter", expanded=True):
        st.subheader("Baujahr und Grunddaten")
        baujahr_optionen = list(U_WERTE_BAUJAHR_TYPISCH.keys())
        st.selectbox("Baualtersklasse des Hauses", options=baujahr_optionen, key="baujahr_haus_str",
                     help="Beeinflusst die U-Wert-Vorschläge.")
        st.radio("Bodenplatte", ["Unterkellert", "Nicht unterkellert"], key="keller_option")

        st.subheader("Flächen (m²)")
        st.number_input("Gesamtfläche Dach", min_value=0.0, step=10.0, key="flaeche_dach")
        st.number_input(f"Gesamtfläche Bodenplatte/{st.session_state.keller_option}", min_value=0.0, step=10.0, key="flaeche_boden")
        st.number_input("Gesamtfläche aller Fenster", min_value=0.0, step=5.0, key="flaeche_fenster_gesamt")

        st.subheader("Außenwände")
        st.number_input("Gesamtfläche Außenwände (m²)", min_value=0.0, step=10.0, key="flaeche_aussenwand_gesamt")
        st.selectbox("Dämmstandard Außenwand (beeinflusst U-Wert Vorschlag)",
                     ["Baujahrstandard", "WDVS (ca. 0.25 W/m²K)", "Passivhaus (ca. 0.15 W/m²K)", "Manuell"],
                     key="daemmstandard_wand")
        
        st.slider("Anteil gedämmter Außenwandfläche (nach gewähltem Standard/manuell)", 0.0, 1.0, key="aussenwand_gedaemmt_anteil", step=0.05)
        flaeche_aw_gedaemmt = st.session_state.flaeche_aussenwand_gesamt * st.session_state.aussenwand_gedaemmt_anteil
        flaeche_aw_ungedaemmt = st.session_state.flaeche_aussenwand_gesamt * (1 - st.session_state.aussenwand_gedaemmt_anteil)
        st.caption(f"Gedämmte Fläche: {flaeche_aw_gedaemmt:.1f} m², Ungedämmte Fläche: {flaeche_aw_ungedaemmt:.1f} m²")


        st.subheader("U-Werte der Bauteile (W/m²K)")
        # U-Wert Logik
        vorschlag_u_wand_standard = get_u_wert_vorschlag(st.session_state.baujahr_haus_str, "Außenwand")
        if st.session_state.daemmstandard_wand == "WDVS (ca. 0.25 W/m²K)":
            vorschlag_u_wand_gedaemmt = 0.25
        elif st.session_state.daemmstandard_wand == "Passivhaus (ca. 0.15 W/m²K)":
            vorschlag_u_wand_gedaemmt = 0.15
        elif st.session_state.daemmstandard_wand == "Manuell":
            vorschlag_u_wand_gedaemmt = st.session_state.u_aussenwand_gedaemmt # Behält manuellen Wert
        else: # Baujahrstandard
            vorschlag_u_wand_gedaemmt = vorschlag_u_wand_standard

        # Setze nur, wenn nicht manuell überschrieben oder wenn Standard gewählt
        if st.session_state.daemmstandard_wand != "Manuell" or 'u_aussenwand_gedaemmt_manually_set' not in st.session_state:
            st.session_state.u_aussenwand_gedaemmt = vorschlag_u_wand_gedaemmt
        # Für ungedämmten Teil immer Baujahrstandard vorschlagen oder alten manuellen Wert behalten
        if 'u_aussenwand_ungedaemmt_manually_set' not in st.session_state:
             st.session_state.u_aussenwand_ungedaemmt = vorschlag_u_wand_standard


        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.number_input("U-Wert gedämmte Außenwand", format="%.2f", key="u_aussenwand_gedaemmt", on_change=lambda: st.session_state.update({'u_aussenwand_gedaemmt_manually_set': True, 'daemmstandard_wand': 'Manuell'}))
            if flaeche_aw_ungedaemmt > 0:
                st.number_input("U-Wert ungedämmte Außenwand", format="%.2f", key="u_aussenwand_ungedaemmt", on_change=lambda: st.session_state.update({'u_aussenwand_ungedaemmt_manually_set': True}))
            else:
                st.session_state.u_aussenwand_ungedaemmt = st.session_state.u_aussenwand_gedaemmt # Setze gleich wenn keine unged. Fläche

            u_d_default = get_u_wert_vorschlag(st.session_state.baujahr_haus_str, "Dach") if 'u_dach_manually_set' not in st.session_state else st.session_state.u_dach
            st.number_input("U-Wert Dach", value=u_d_default, format="%.2f", key="u_dach", on_change=lambda: st.session_state.update({'u_dach_manually_set': True}))
        with col_u2:
            u_b_default = get_u_wert_vorschlag(st.session_state.baujahr_haus_str, "Bodenplatte") if 'u_boden_manually_set' not in st.session_state else st.session_state.u_boden
            st.number_input(f"U-Wert Bodenplatte/{st.session_state.keller_option}", value=u_b_default, format="%.2f", key="u_boden", on_change=lambda: st.session_state.update({'u_boden_manually_set': True}))
            
            fenster_baujahr_optionen = list(FENSTER_U_WERTE_BAUJAHR.keys())
            st.selectbox("Baualtersklasse Fenster", options=fenster_baujahr_optionen, key="fenster_baujahr_str")
            u_f_default = get_fenster_u_wert_vorschlag(st.session_state.fenster_baujahr_str) if 'u_fenster_manually_set' not in st.session_state else st.session_state.u_fenster
            st.number_input("U-Wert Fenster (Mittelwert)", value=u_f_default, format="%.2f", key="u_fenster", on_change=lambda: st.session_state.update({'u_fenster_manually_set': True}))

        H_T_wand = (st.session_state.u_aussenwand_gedaemmt * flaeche_aw_gedaemmt) + \
                   (st.session_state.u_aussenwand_ungedaemmt * flaeche_aw_ungedaemmt if flaeche_aw_ungedaemmt > 0 else 0)
        H_T_dach = st.session_state.u_dach * st.session_state.flaeche_dach
        H_T_boden = st.session_state.u_boden * st.session_state.flaeche_boden
        H_T_fenster = st.session_state.u_fenster * st.session_state.flaeche_fenster_gesamt
        H_T_gesamt = H_T_wand + H_T_dach + H_T_boden + H_T_fenster
        H_L_pauschal_faktor = 0.15
        H_TR_gesamt_mit_lueftung = H_T_gesamt * (1 + H_L_pauschal_faktor)

        st.metric("Spezifischer Transmissionswärmeverlustkoeffizient $H_T$ (ohne Lüftung)", f"{H_T_gesamt:.2f} W/K")
        st.metric("Gesamtwärmeverlustkoeffizient $H_{TR}$ (inkl. pauschaler Lüftung)", f"{H_TR_gesamt_mit_lueftung:.2f} W/K")

    with st.expander("2. Referenzklima & Heizwärmebedarf", expanded=True):
        # ... (Klimagrafik und Heizwärmebedarfsberechnung wie zuvor) ...
        fig_temp = px.line(REFERENCE_TEMP_PROFILE, x="Monat", y=["Mitteltemperatur", "Min-Temperatur", "Max-Temperatur"],
                       labels={"value": "Temperatur (°C)", "variable": "Profil"}, markers=True)
        st.plotly_chart(fig_temp, use_container_width=True)
        monatsdaten = REFERENCE_TEMP_PROFILE.copy()
        monatsdaten["HeizbedarfAktiv"] = (monatsdaten["Mitteltemperatur"] < HEIZGRENZE_TEMP) & \
                                        (RAUMTEMPERATUR_SOLL > monatsdaten["Mitteltemperatur"])
        monatsdaten["DeltaT_Heizung"] = np.maximum(0, RAUMTEMPERATUR_SOLL - monatsdaten["Mitteltemperatur"])
        monatsdaten["Heizstunden"] = monatsdaten["TageImMonat"] * 24 * monatsdaten["HeizbedarfAktiv"]
        monatsdaten["Heizwaermebedarf_kWh"] = (H_TR_gesamt_mit_lueftung * monatsdaten["DeltaT_Heizung"] * monatsdaten["Heizstunden"]) / 1000
        Q_H_jahr = monatsdaten["Heizwaermebedarf_kWh"].sum()
        st.metric("Jährlicher Heizwärmebedarf (Gebäude)", f"{Q_H_jahr:,.0f} kWh/a")
        heizbedarf_monatlich_df = monatsdaten[["Monat", "MonatNr", "TageImMonat", "Heizwaermebedarf_kWh"]].copy()
        heizbedarf_monatlich_df.rename(columns={"Heizwaermebedarf_kWh": "Heizung"}, inplace=True)


with tab2: # PV & Weitere Verbräuche
    with st.expander("3. PV-Anlage", expanded=True):
        st.checkbox("PV-Anlage berücksichtigen?", key="use_pv")
        pv_ertrag_monatlich_kWh = pd.Series([0.0]*12, index=range(1,13))

        if st.session_state.use_pv:
            col3a, col3b, col3c = st.columns(3)
            with col3a:
                st.number_input("Installierte PV-Leistung (kWp)", min_value=0.0, step=0.5, key="pv_kwp")
                st.slider("Spezifischer Jahresertrag (kWh/kWp/a)", 700, 1300, key="spez_jahresertrag_pv")
            with col3b:
                st.selectbox("Ausrichtung PV-Anlage", ["Süd", "Süd-Ost/Süd-West", "Ost/West", "Nord (Flachdach)"], key="pv_ausrichtung")
                ausrichtungsfaktoren = {"Süd": 1.0, "Süd-Ost/Süd-West": 0.95, "Ost/West": 0.88, "Nord (Flachdach)": 0.75}
                faktor_ausrichtung = ausrichtungsfaktoren[st.session_state.pv_ausrichtung]
            with col3c:
                st.slider("Neigungswinkel PV-Anlage (°)", 0, 90, key="pv_neigung")
                faktor_neigung = 1.0 - (abs(st.session_state.pv_neigung - 35) / 90) * 0.3
            
            pv_gesamtertrag_jahr = st.session_state.pv_kwp * st.session_state.spez_jahresertrag_pv * faktor_ausrichtung * faktor_neigung
            st.metric("Geschätzter jährlicher PV-Gesamtertrag", f"{pv_gesamtertrag_jahr:,.0f} kWh/a")

            for monat_nr_map, rel_anteil in PV_ERTRAG_PROFIL_RELATIV.items():
                 pv_ertrag_monatlich_kWh[monat_nr_map] = pv_gesamtertrag_jahr * rel_anteil
            
            st.checkbox("PV-Speicher berücksichtigen?", key="use_speicher")
            if st.session_state.use_speicher:
                st.number_input("Speicherkapazität (kWh)", min_value=0.0, step=0.5, key="speicher_kwh")
                speicher_wirkungsgrad = 0.9 # Annahme
            else:
                speicher_wirkungsgrad = 1.0
            
            pv_strategie_optionen = [
                "Maximale Einspeisung (Netz zuerst)",
                "Eigenverbrauch priorisieren (Haushalt > WP > Speicher > Netz)",
                "Eigenverbrauch stark priorisieren (Haushalt > Speicher > WP > Netz)"
            ]
            st.selectbox("PV Strom Nutzungsstrategie", pv_strategie_optionen, key="pv_nutzungs_strategie")
            st.number_input("Anpassung Investitionskosten PV/Speicher (€)", step=100.0, key="invest_adj_pv",
                             help="Zusätzliche Kosten (+) oder Einsparungen (-), z.B. durch spezielle Förderungen oder Eigenleistung.")
        else:
            pv_gesamtertrag_jahr = 0.0

    with st.expander("4. Weitere Energieverbräuche", expanded=True):
        st.subheader("Energiebedarf für Brauchwasser")
        bedarf_ww_person_jahr_basis = 600 # kWh
        # Korrigierte Formel für Energiesparfaktor-Auswirkung
        bedarf_ww_jahr_gesamt = st.session_state.anzahl_personen * bedarf_ww_person_jahr_basis * (1 - (st.session_state.energiesparfaktor_allgemein * 0.5))
        bedarf_ww_monatlich_wert = bedarf_ww_jahr_gesamt / 12
        st.metric("Jährlicher Energiebedarf Brauchwasser", f"{bedarf_ww_jahr_gesamt:,.0f} kWh/a")

        st.subheader("Energiebedarf Haushaltsstrom (ohne Heizung/WW-Erzeugung)")
        bedarf_strom_person_jahr_basis_kWh = 1000 # kWh/Person (reiner Verbrauchsteil)
        grundlast_pro_wohneinheit_kWh = 800 # kWh/WE (z.B. für Kühlschrank etc. einer WE)
        anzahl_haushalte_approx = max(1, round(st.session_state.anzahl_personen / 2.5)) # Grobe Schätzung Anzahl Wohneinheiten
        
        # Berechnung Haushaltsstrom
        bedarf_strom_jahr_berechnet = (st.session_state.anzahl_personen * bedarf_strom_person_jahr_basis_kWh + \
                                    anzahl_haushalte_approx * grundlast_pro_wohneinheit_kWh) * \
                                    (1 - st.session_state.energiesparfaktor_allgemein)
        
        st.markdown(f"Berechneter Basis-Haushaltsstrombedarf (vor manueller Korrektur): **{bedarf_strom_jahr_berechnet:,.0f} kWh/a**")
        st.number_input("Manuelle Angabe Jahres-Haushaltsstrombedarf (kWh/a, 0 = Berechnung nutzen)",
                        min_value=0.0, step=100.0, key="haushaltstrom_manuell_kWh")

        if st.session_state.haushaltstrom_manuell_kWh > 0:
            bedarf_strom_jahr_final = st.session_state.haushaltstrom_manuell_kWh
            st.info("Manueller Haushaltsstrombedarf wird verwendet.")
        else:
            bedarf_strom_jahr_final = bedarf_strom_jahr_berechnet
        
        bedarf_strom_monatlich_wert = bedarf_strom_jahr_final / 12
        st.metric("Finaler jährlicher Energiebedarf Haushaltsstrom", f"{bedarf_strom_jahr_final:,.0f} kWh/a")

    # Sammle alle Bedarfe für die Visualisierung (wird später für Plots gebraucht)
    energiebilanz_df_basis = pd.DataFrame({"Monat": REFERENCE_TEMP_PROFILE["Monat"], "MonatNr": REFERENCE_TEMP_PROFILE["MonatNr"]})
    energiebilanz_df_basis["Heizung"] = heizbedarf_monatlich_df["Heizung"].values
    energiebilanz_df_basis["Brauchwasser"] = bedarf_ww_monatlich_wert
    energiebilanz_df_basis["Haushaltsstrom"] = bedarf_strom_monatlich_wert
    energiebilanz_df_basis["PV_Erzeugung"] = pv_ertrag_monatlich_kWh.values if st.session_state.use_pv else 0.0


with tab3: # Systemvergleich & Kosten
    st.header("Heizsystemvergleich & Wirtschaftlichkeit")
    st.subheader("Anpassung Investitionskosten Heizsysteme")
    st.selectbox("Vorhandenes Heizsystem (Beeinflusst ggf. Ihre manuelle Kostenanpassung)", 
                 ["Keines", "Alte Gasheizung", "Alte Ölheizung", "Alte Wärmepumpe", "Sonstiges"], 
                 key="vorhandenes_heizsystem")
    st.caption("Passen Sie ggf. die Investitionskosten für die *neuen* Heizsysteme an (z.B. Restwert Altgerät, spezielle Boni, Eigenleistung):")
    col_invest_adj1, col_invest_adj2, col_invest_adj3 = st.columns(3)
    with col_invest_adj1:
        st.number_input("Anpassung Invest. Gas (€)", step=100.0, key="invest_adj_gas", help="-Wert für Reduktion, +Wert für Erhöhung")
    with col_invest_adj2:
        st.number_input("Anpassung Invest. WP (€)", step=100.0, key="invest_adj_wp")
    with col_invest_adj3:
        st.number_input("Anpassung Invest. FW (€)", step=100.0, key="invest_adj_fw")

    system_parameter = {
        "Gasheizung": {"effizienz": 0.90, "brennstoff": "Gas", "strombedarf_anteil": 0.02,
                       "inst_kosten_fix": 6000, "inst_kosten_leistung": 500, "wartung_pa": 300, # leicht erhöht
                       "invest_adj_key": "invest_adj_gas"},
        "Wärmepumpe (Luft-Wasser)": {"effizienz": 3.5, "brennstoff": "Strom", "strombedarf_anteil": 1.0,
                                     "inst_kosten_fix": 15000, "inst_kosten_leistung": 700, "wartung_pa": 250, # leicht erhöht
                                     "invest_adj_key": "invest_adj_wp"},
        "Fernwärme": {"effizienz": 0.98, "brennstoff": "Fernwärme", "strombedarf_anteil": 0.01,
                       "inst_kosten_fix": 8000, "inst_kosten_leistung": 300, "wartung_pa": 150, # leicht erhöht
                       "invest_adj_key": "invest_adj_fw"}
    }
    delta_T_norm_auslegung = RAUMTEMPERATUR_SOLL - (-14)
    heizlast_kW = (H_TR_gesamt_mit_lueftung * delta_T_norm_auslegung) / 1000

    # --- Berechnungsfunktion (bleibt im Kern ähnlich, aber Investitionskosten PV ausgelagert) ---
    def berechne_system_details_v2(system_name, Q_H_monat_df_param, Q_WW_monat_param, E_HH_monat_param_array,
                                E_PV_monatlich_param, pv_nutz_strat_param, 
                                use_speicher_param, speicher_kwh_param_effective, speicher_wg_param,
                                preise_param, heizlast_param_kw):
        params = system_parameter[system_name]
        effizienz = params["effizienz"]
        
        # ... (Kernlogik für Energieflüsse, PV-Nutzung, Speicher bleibt wie in der vorherigen Version) ...
        monatliche_heizlast_heizsystem = (Q_H_monat_df_param["Heizung"].values + Q_WW_monat_param) / effizienz
        monatliche_brennstoff_heizsystem = monatliche_heizlast_heizsystem.copy()
        monatliche_strom_fuer_heizsystem = np.zeros(12)

        if params["brennstoff"] == "Strom": # Wärmepumpe
            monatliche_strom_fuer_heizsystem += monatliche_heizlast_heizsystem
            monatliche_brennstoff_heizsystem = np.zeros(12)
        else: # Gas, Fernwärme
             monatliche_strom_fuer_heizsystem += monatliche_heizlast_heizsystem * params["strombedarf_anteil"]
             monatliche_brennstoff_heizsystem *= (1 - params["strombedarf_anteil"])
        
        monatlicher_strombedarf_gesamt_ohne_pv = E_HH_monat_param_array + monatliche_strom_fuer_heizsystem # E_HH_monat_param_array ist jetzt ein Array

        # PV-Nutzung und Speicherlogik (vereinfacht monatlich)
        pv_direktverbrauch_monatlich = np.zeros(12)
        pv_einspeisung_monatlich = np.zeros(12)
        pv_ladung_speicher_monatlich = np.zeros(12)
        speicher_entladung_monatlich = np.zeros(12)
        netzbezug_strom_monatlich = np.zeros(12)
        aktueller_speicherstand_kwh = 0.0 

        for i in range(12):
            pv_aktuell_monat = E_PV_monatlich_param.iloc[i] if st.session_state.use_pv else 0.0
            strombedarf_aktuell_monat = monatlicher_strombedarf_gesamt_ohne_pv[i]
            
            pv_ueberschuss = pv_aktuell_monat
            strom_defizit = strombedarf_aktuell_monat
            
            # Strategie Anwendung (gekürzt dargestellt, Logik wie zuvor)
            if pv_nutz_strat_param == "Maximale Einspeisung (Netz zuerst)":
                # Vereinfachung: 20% des PV-Ertrags wird direkt verbraucht, wenn Bedarf da ist
                direktverbrauch = min(pv_ueberschuss * 0.2, strom_defizit)
                pv_direktverbrauch_monatlich[i] += direktverbrauch
                strom_defizit -= direktverbrauch
                pv_ueberschuss -= direktverbrauch
                pv_einspeisung_monatlich[i] += pv_ueberschuss 
                pv_ueberschuss = 0 
            elif pv_nutz_strat_param == "Eigenverbrauch priorisieren (Haushalt > WP > Speicher > Netz)":
                direktverbrauch = min(pv_ueberschuss, strom_defizit)
                pv_direktverbrauch_monatlich[i] += direktverbrauch
                strom_defizit -= direktverbrauch
                pv_ueberschuss -= direktverbrauch
                if pv_ueberschuss > 0 and use_speicher_param and speicher_kwh_param_effective > 0:
                    ladung_moeglich = speicher_kwh_param_effective - aktueller_speicherstand_kwh
                    ladung_effektiv_brutto = min(pv_ueberschuss, ladung_moeglich / speicher_wg_param)
                    pv_ladung_speicher_monatlich[i] = ladung_effektiv_brutto
                    aktueller_speicherstand_kwh += ladung_effektiv_brutto * speicher_wg_param
                    pv_ueberschuss -= ladung_effektiv_brutto
                pv_einspeisung_monatlich[i] += pv_ueberschuss
            elif pv_nutz_strat_param == "Eigenverbrauch stark priorisieren (Haushalt > Speicher > WP > Netz)":
                # Annahme: E_HH_monat_param_array[i] ist der Haushaltsstromanteil für diesen Monat
                direktverbrauch_hh_anteil = min(pv_ueberschuss, E_HH_monat_param_array[i])
                pv_direktverbrauch_monatlich[i] += direktverbrauch_hh_anteil
                rest_strombedarf_fuer_wp = max(0, strom_defizit - direktverbrauch_hh_anteil)
                pv_ueberschuss_nach_hh = pv_ueberschuss - direktverbrauch_hh_anteil
                
                if pv_ueberschuss_nach_hh > 0 and use_speicher_param and speicher_kwh_param_effective > 0:
                    ladung_moeglich = speicher_kwh_param_effective - aktueller_speicherstand_kwh
                    ladung_effektiv_brutto = min(pv_ueberschuss_nach_hh, ladung_moeglich / speicher_wg_param)
                    pv_ladung_speicher_monatlich[i] = ladung_effektiv_brutto
                    aktueller_speicherstand_kwh += ladung_effektiv_brutto * speicher_wg_param
                    pv_ueberschuss_nach_hh -= ladung_effektiv_brutto

                direktverbrauch_wp_anteil = min(pv_ueberschuss_nach_hh, rest_strombedarf_fuer_wp)
                pv_direktverbrauch_monatlich[i] += direktverbrauch_wp_anteil
                strom_defizit = max(0, strom_defizit - (direktverbrauch_hh_anteil + direktverbrauch_wp_anteil))
                pv_ueberschuss_nach_wp = pv_ueberschuss_nach_hh - direktverbrauch_wp_anteil
                pv_einspeisung_monatlich[i] += pv_ueberschuss_nach_wp

            if strom_defizit > 0 and use_speicher_param and aktueller_speicherstand_kwh > 0:
                entladung_netto = min(strom_defizit, aktueller_speicherstand_kwh * speicher_wg_param)
                entladung_brutto = entladung_netto / speicher_wg_param
                speicher_entladung_monatlich[i] = entladung_brutto
                aktueller_speicherstand_kwh -= entladung_brutto
                strom_defizit -= entladung_netto
            netzbezug_strom_monatlich[i] = max(0, strom_defizit)

        # ... (Kostenberechnung wie zuvor) ...
        kosten_strom_bezug = np.sum(netzbezug_strom_monatlich) * preise_param["strom"]
        erloes_einspeisung = np.sum(pv_einspeisung_monatlich) * preise_param["einspeisung"]
        kosten_brennstoff_heizsystem = 0
        if params["brennstoff"] == "Gas": kosten_brennstoff_heizsystem = np.sum(monatliche_brennstoff_heizsystem) * preise_param["gas"]
        elif params["brennstoff"] == "Fernwärme": kosten_brennstoff_heizsystem = np.sum(monatliche_brennstoff_heizsystem) * preise_param["fernwaerme"]
        laufende_energiekosten_jahr = kosten_strom_bezug + kosten_brennstoff_heizsystem - erloes_einspeisung
        wartungskosten_jahr = params["wartung_pa"]
        gesamte_laufende_kosten_jahr = laufende_energiekosten_jahr + wartungskosten_jahr

        invest_basis = params["inst_kosten_fix"] + params["inst_kosten_leistung"] * heizlast_param_kw
        invest_manuelle_anpassung = st.session_state.get(params["invest_adj_key"], 0)
        installationskosten_heizsystem_anteil = invest_basis + invest_manuelle_anpassung
        
        return {
            "name": system_name,
            "installationskosten_system_anteil": installationskosten_heizsystem_anteil,
            "laufende_energiekosten_jahr": laufende_energiekosten_jahr,
            "wartungskosten_jahr": wartungskosten_jahr,
            "gesamte_laufende_kosten_jahr": gesamte_laufende_kosten_jahr,
            "jahresverbrauch_strom_netz": np.sum(netzbezug_strom_monatlich),
            "jahresverbrauch_gas": np.sum(monatliche_brennstoff_heizsystem) if params["brennstoff"] == "Gas" else 0,
            "jahresverbrauch_fernwaerme": np.sum(monatliche_brennstoff_heizsystem) if params["brennstoff"] == "Fernwärme" else 0,
            "pv_direktverbrauch_jahr": np.sum(pv_direktverbrauch_monatlich),
            "pv_einspeisung_jahr": np.sum(pv_einspeisung_monatlich),
            "monatlicher_strom_netzbezug": netzbezug_strom_monatlich, # Für Plots
            "monatlicher_strom_heizsystem": monatliche_strom_fuer_heizsystem, # Für Plots
        }

    # Berechnungen für alle Systeme
    heizsystem_optionen_alle = ["Gasheizung", "Wärmepumpe (Luft-Wasser)", "Fernwärme"]
    preis_dict = {"strom": st.session_state.strompreis, "gas": st.session_state.gaspreis, 
                  "fernwaerme": st.session_state.fernwaermepreis, "einspeisung": st.session_state.einspeiseverguetung}
    
    results_all_systems_details = []
    for system_name_iter in heizsystem_optionen_alle:
        details = berechne_system_details_v2(
            system_name_iter, 
            heizbedarf_monatlich_df, 
            bedarf_ww_monatlich_wert, 
            energiebilanz_df_basis["Haushaltsstrom"].values, # Als Array übergeben
            pv_ertrag_monatlich_kWh, 
            st.session_state.pv_nutzungs_strategie,
            st.session_state.use_speicher, 
            st.session_state.speicher_kwh if st.session_state.use_speicher else 0.0, 
            speicher_wirkungsgrad if st.session_state.use_speicher else 1.0, 
            preis_dict, 
            heizlast_kW
        )
        results_all_systems_details.append(details)
    
    st.subheader("Wirtschaftlichkeitsübersicht (Jahr 1)")
    
    # PV Kosten separat
    installationskosten_pv_final = 0
    if st.session_state.use_pv:
        basis_invest_pv = st.session_state.pv_kwp * 1400 # Annahme €/kWp
        if st.session_state.use_speicher and st.session_state.speicher_kwh > 0:
            basis_invest_pv += st.session_state.speicher_kwh * 800 # Annahme €/kWh
        installationskosten_pv_final = basis_invest_pv + st.session_state.invest_adj_pv
        st.metric("Investitionskosten PV-Anlage & Speicher (inkl. Anpassung)", f"{installationskosten_pv_final:,.0f} €")
    else:
        st.info("Keine PV-Anlage ausgewählt.")

    cols_results_display = st.columns(len(results_all_systems_details))
    for i, res_detail in enumerate(results_all_systems_details):
        with cols_results_display[i]:
            st.markdown(f"#### {res_detail['name']}")
            gesamte_invest_heizsystem_pv = res_detail['installationskosten_system_anteil'] + (installationskosten_pv_final if st.session_state.use_pv else 0)
            st.metric("Investitionskosten Heizsystem", f"{res_detail['installationskosten_system_anteil']:,.0f} €")
            if st.session_state.use_pv:
                st.metric("Gesamte Investition (mit PV)", f"{gesamte_invest_heizsystem_pv:,.0f} €")

            st.metric("Laufende Energiekosten/Jahr", f"{res_detail['laufende_energiekosten_jahr']:,.0f} €")
            st.metric("Wartungskosten/Jahr", f"{res_detail['wartungskosten_jahr']:,.0f} €")
            st.metric("Gesamte laufende Kosten/Jahr", f"{res_detail['gesamte_laufende_kosten_jahr']:,.0f} €")
            # ... (Weitere Detailausgaben wie Jahresverbräuche etc.)
            st.markdown("---")
            st.write(f"Netzbezug Strom: {res_detail['jahresverbrauch_strom_netz']:,.0f} kWh/a")
            if res_detail['jahresverbrauch_gas'] > 0: st.write(f"Gasbezug: {res_detail['jahresverbrauch_gas']:,.0f} kWh/a")
            if res_detail['jahresverbrauch_fernwaerme'] > 0: st.write(f"Fernwärmebezug: {res_detail['jahresverbrauch_fernwaerme']:,.0f} kWh/a")
            if st.session_state.use_pv:
                st.write(f"PV Direktverbrauch: {res_detail['pv_direktverbrauch_jahr']:,.0f} kWh/a")
                st.write(f"PV Einspeisung: {res_detail['pv_einspeisung_jahr']:,.0f} kWh/a")


    # --- Monatliche Energiebilanz Grafik (Beispiel für erstes System) ---
    st.subheader(f"Monatliche Energiebilanz für: {results_all_systems_details[0]['name']}")
    # ... (Plotting Code wie zuvor, angepasst an neue Datenstruktur falls nötig) ...
    vis_df_monthly_plot = energiebilanz_df_basis.copy()
    vis_df_monthly_plot["Strom_Heizsystem"] = results_all_systems_details[0]['monatlicher_strom_heizsystem']
    # (Netzbezug etc. könnten auch geplottet werden)
    
    plot_data_monthly_fig = pd.DataFrame({
        "Monat": vis_df_monthly_plot["Monat"],
        "Heizwärmebedarf": vis_df_monthly_plot["Heizung"],
        "Warmwasserbedarf": vis_df_monthly_plot["Brauchwasser"],
        "Haushaltsstrombedarf": vis_df_monthly_plot["Haushaltsstrom"],
        "Strombedarf Heizsystem": vis_df_monthly_plot["Strom_Heizsystem"],
        "PV Erzeugung": vis_df_monthly_plot["PV_Erzeugung"] * -1 # Negativ für Darstellung
    })
    fig_energy_balance_monthly_display = go.Figure()
    for col_name_plot in ["Heizwärmebedarf", "Warmwasserbedarf", "Haushaltsstrombedarf", "Strombedarf Heizsystem", "PV Erzeugung"]:
        fig_energy_balance_monthly_display.add_trace(go.Bar(x=plot_data_monthly_fig["Monat"], y=plot_data_monthly_fig[col_name_plot], name=col_name_plot))
    fig_energy_balance_monthly_display.update_layout(barmode='relative', title_text='Monatliche Energieflüsse (Bedarfe vs. PV Erzeugung)',
                                     xaxis_title="Monat", yaxis_title="Energie (kWh)")
    st.plotly_chart(fig_energy_balance_monthly_display, use_container_width=True)


    # --- 15-JAHRES-PROGNOSE ---
    st.subheader(f"{st.session_state.prognose_jahre}-Jahres-Kostenprognose")
    # ... (Prognose-Logik wie zuvor, aber Gesamte Investitionskosten richtig berücksichtigen) ...
    prognose_daten_liste_final = []
    ps_strom_val = st.session_state.preissteigerung_strom / 100
    ps_gas_val = st.session_state.preissteigerung_gas / 100
    ps_fw_val = st.session_state.preissteigerung_fernwaerme / 100

    for res_system_prog in results_all_systems_details:
        system_name_prog = res_system_prog["name"]
        kum_kosten_prog = res_system_prog['installationskosten_system_anteil'] + (installationskosten_pv_final if st.session_state.use_pv else 0)
        
        current_strompreis_prog = st.session_state.strompreis
        current_gaspreis_prog = st.session_state.gaspreis
        current_fernwaermepreis_prog = st.session_state.fernwaermepreis
        current_einspeiseverguetung_prog = st.session_state.einspeiseverguetung

        for jahr_prog in range(1, int(st.session_state.prognose_jahre) + 1):
            # ... (Berechnung laufende Kosten pro Jahr mit Preissteigerung) ...
            # (Code identisch zur vorherigen Prognoseberechnung, hier gekürzt)
            aktuelle_preise_prognose_jahr_val = {
                "strom": current_strompreis_prog, "gas": current_gaspreis_prog,
                "fernwaerme": current_fernwaermepreis_prog, "einspeisung": current_einspeiseverguetung_prog
            }
            kosten_strom_bezug_prognose_val = res_system_prog["jahresverbrauch_strom_netz"] * aktuelle_preise_prognose_jahr_val["strom"]
            erloes_einspeisung_prognose_val = res_system_prog["pv_einspeisung_jahr"] * aktuelle_preise_prognose_jahr_val["einspeisung"]
            kosten_brennstoff_prognose_val = 0
            if res_system_prog["jahresverbrauch_gas"] > 0: kosten_brennstoff_prognose_val = res_system_prog["jahresverbrauch_gas"] * aktuelle_preise_prognose_jahr_val["gas"]
            elif res_system_prog["jahresverbrauch_fernwaerme"] > 0: kosten_brennstoff_prognose_val = res_system_prog["jahresverbrauch_fernwaerme"] * aktuelle_preise_prognose_jahr_val["fernwaerme"]
            laufende_energiekosten_prognose_jahr_val = kosten_strom_bezug_prognose_val + kosten_brennstoff_prognose_val - erloes_einspeisung_prognose_val
            gesamte_laufende_kosten_prognose_jahr_val = laufende_energiekosten_prognose_jahr_val + res_system_prog["wartungskosten_jahr"]
            
            kum_kosten_prog += gesamte_laufende_kosten_prognose_jahr_val
            prognose_daten_liste_final.append({
                "System": system_name_prog, "Jahr": jahr_prog,
                "Laufende Kosten": gesamte_laufende_kosten_prognose_jahr_val,
                "Kumulierte Kosten": kum_kosten_prog
            })
            current_strompreis_prog *= (1 + ps_strom_val)
            current_gaspreis_prog *= (1 + ps_gas_val)
            current_fernwaermepreis_prog *= (1 + ps_fw_val)

    prognose_df_output = pd.DataFrame(prognose_daten_liste_final)
    if not prognose_df_output.empty:
        fig_prognose_output = px.line(prognose_df_output, x="Jahr", y="Kumulierte Kosten", color="System",
                               title=f"Kumulierte Gesamtkosten über {st.session_state.prognose_jahre} Jahre", markers=True)
        st.plotly_chart(fig_prognose_output, use_container_width=True)
        # ... (Empfehlungstext wie zuvor) ...
        beste_option_ende_df_val = prognose_df_output[prognose_df_output["Jahr"] == int(st.session_state.prognose_jahre)]
        if not beste_option_ende_df_val.empty:
            beste_option_ende_val = beste_option_ende_df_val.sort_values("Kumulierte Kosten").iloc[0]
            st.success(f"Basierend auf der {st.session_state.prognose_jahre}-Jahres-Prognose stellt **{beste_option_ende_val['System']}** "
                       f"voraussichtlich die kostengünstigste Option dar, mit kumulierten Kosten von "
                       f"{beste_option_ende_val['Kumulierte Kosten']:,.0f} €.")


with tab4: # Tagesprofil & Export
    st.header("Tagesprofil & PDF-Export")
    # --- TAGESPROFIL VISUALISIERUNG (Code wie zuvor) ---
    st.subheader("Typischer Tagesverlauf Energieflüsse (für einen ausgewählten Monat)")
    monat_wahl_tag_display = st.selectbox("Monat für Tagesprofil wählen:", options=REFERENCE_TEMP_PROFILE["Monat"], index=0, key="tagesprofil_monat_wahl")
    
    idx_monat_display = REFERENCE_TEMP_PROFILE[REFERENCE_TEMP_PROFILE["Monat"] == monat_wahl_tag_display].index[0]
    tage_im_monat_display = REFERENCE_TEMP_PROFILE.loc[idx_monat_display, "TageImMonat"]
    
    pv_tag_avg_display = (pv_ertrag_monatlich_kWh.iloc[idx_monat_display] / tage_im_monat_display) if st.session_state.use_pv else 0
    hh_tag_avg_display = bedarf_strom_monatlich_wert # Ist bereits Durchschnitt pro Tag des Monats, wenn man es so sieht
    dhw_tag_avg_display = bedarf_ww_monatlich_wert
    heiz_tag_avg_display = heizbedarf_monatlich_df[heizbedarf_monatlich_df["Monat"] == monat_wahl_tag_display]["Heizung"].iloc[0] / tage_im_monat_display
    
    sys1_strom_heiz_monat_display = results_all_systems_details[0]["monatlicher_strom_heizsystem"][idx_monat_display]
    heizsystem_strom_tag_avg_display = sys1_strom_heiz_monat_display / tage_im_monat_display
    
    stunden_display = list(range(24))
    tagesprofil_df_display = pd.DataFrame({"Stunde": stunden_display})
    tagesprofil_df_display["PV_Erzeugung_kWh"] = pv_daily_shape * pv_tag_avg_display
    tagesprofil_df_display["Haushaltsstrom_kWh"] = hh_daily_shape * hh_tag_avg_display
    tagesprofil_df_display["Warmwasser_kWh"] = dhw_daily_shape * dhw_tag_avg_display
    tagesprofil_df_display["Heizung_Energetisch_kWh"] = heating_daily_shape * heiz_tag_avg_display
    tagesprofil_df_display["Strom_Heizsystem_kWh"] = heating_daily_shape * heizsystem_strom_tag_avg_display # Annahme: Heizprofil = Stromprofil WP

    tagesprofil_df_display["Gesamtstrombedarf_kWh"] = tagesprofil_df_display["Haushaltsstrom_kWh"] + tagesprofil_df_display["Strom_Heizsystem_kWh"]
    tagesprofil_df_display["PV_Direktverbrauch_kWh"] = np.minimum(tagesprofil_df_display["PV_Erzeugung_kWh"], tagesprofil_df_display["Gesamtstrombedarf_kWh"])
    tagesprofil_df_display["Netzbezug_kWh"] = np.maximum(0, tagesprofil_df_display["Gesamtstrombedarf_kWh"] - tagesprofil_df_display["PV_Direktverbrauch_kWh"])
    tagesprofil_df_display["Einspeisung_kWh"] = np.maximum(0, tagesprofil_df_display["PV_Erzeugung_kWh"] - tagesprofil_df_display["PV_Direktverbrauch_kWh"])

    fig_tagesprofil_display = go.Figure()
    # ... (Plotting Code wie zuvor) ...
    fig_tagesprofil_display.add_trace(go.Scatter(x=tagesprofil_df_display["Stunde"], y=tagesprofil_df_display["Gesamtstrombedarf_kWh"], name="Gesamtstrombedarf (HH+Heiz.)", line_shape='spline', fill='tozeroy'))
    if st.session_state.use_pv: fig_tagesprofil_display.add_trace(go.Scatter(x=tagesprofil_df_display["Stunde"], y=tagesprofil_df_display["PV_Erzeugung_kWh"], name="PV Erzeugung", line_shape='spline', fill='tozeroy'))
    fig_tagesprofil_display.add_trace(go.Scatter(x=tagesprofil_df_display["Stunde"], y=tagesprofil_df_display["Netzbezug_kWh"], name="Netzbezug", line_shape='spline'))
    if st.session_state.use_pv: fig_tagesprofil_display.add_trace(go.Scatter(x=tagesprofil_df_display["Stunde"], y=tagesprofil_df_display["Einspeisung_kWh"], name="Einspeisung", line_shape='spline'))
    fig_tagesprofil_display.update_layout(title=f"Typischer Tagesverlauf im {monat_wahl_tag_display} (vereinfacht, für {results_all_systems_details[0]['name']})",
                                 xaxis_title="Stunde des Tages", yaxis_title="Energie (kWh)")
    st.plotly_chart(fig_tagesprofil_display, use_container_width=True)


    # --- PDF EXPORT ---
    st.subheader("PDF-Export der Ergebnisse")
    if st.button("PDF generieren und herunterladen"):
        pdf = PDF()
        pdf.add_page()
        
        # Kapitel 1: Allgemeine Daten
        pdf.chapter_title("1. Allgemeine Projektdaten")
        allg_daten = {
            "Projekt": f"{st.session_state.user_name} - {st.session_state.project_name}",
            "Datum": datetime.now().strftime('%d.%m.%Y'),
            "Anzahl Personen": st.session_state.anzahl_personen,
            "Energiespar-Faktor": f"{st.session_state.energiesparfaktor_allgemein:.2f}",
        }
        pdf.chapter_body(allg_daten)

        # Kapitel 2: Gebäudedaten
        pdf.chapter_title("2. Gebäudedaten & Wärmebedarf")
        geb_daten = {
            "Baualtersklasse": st.session_state.baujahr_haus_str,
            "Gesamt H_TR": f"{H_TR_gesamt_mit_lueftung:.2f} W/K",
            "Jährl. Heizwärmebedarf": f"{Q_H_jahr:,.0f} kWh/a",
            "Jährl. Brauchwasserbedarf": f"{bedarf_ww_jahr_gesamt:,.0f} kWh/a",
            "Jährl. Haushaltsstrombedarf": f"{bedarf_strom_jahr_final:,.0f} kWh/a",
        }
        # U-Werte etc. könnten hier noch detaillierter hinzugefügt werden
        pdf.chapter_body(geb_daten)
        pdf.add_plotly_fig(fig_temp, title="Jahrestemperaturprofil") # Beispiel Grafik

        # Kapitel 3: PV-Anlage
        if st.session_state.use_pv:
            pdf.chapter_title("3. PV-Anlage")
            pv_daten_pdf = {
                "Installierte Leistung": f"{st.session_state.pv_kwp:.1f} kWp",
                "Jahresertrag (geschätzt)": f"{pv_gesamtertrag_jahr:,.0f} kWh/a",
                "Speicher": f"{st.session_state.speicher_kwh if st.session_state.use_speicher else 0:.1f} kWh" if st.session_state.use_speicher else "Kein Speicher",
                "Nutzungsstrategie": st.session_state.pv_nutzungs_strategie,
                "Investitionskosten PV (angepasst)": f"{installationskosten_pv_final:,.0f} EUR"
            }
            pdf.chapter_body(pv_daten_pdf)
            pdf.add_plotly_fig(fig_energy_balance_monthly_display, title="Monatliche Energiebilanz (Beispiel)")


        # Kapitel 4: Wirtschaftlichkeitsübersicht
        pdf.chapter_title("4. Wirtschaftlichkeitsübersicht (Jahr 1)")
        for res_pdf in results_all_systems_details:
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 7, res_pdf['name'], 0, 1)
            pdf.set_font('Arial', '', 10)
            invest_sys_pdf = res_pdf['installationskosten_system_anteil'] + (installationskosten_pv_final if st.session_state.use_pv else 0)
            sys_body = {
                "Investition (mit PV-Anteil)": f"{invest_sys_pdf:,.0f} EUR",
                "Laufende Energiekosten/Jahr": f"{res_pdf['laufende_energiekosten_jahr']:,.0f} EUR",
                "Gesamte laufende Kosten/Jahr": f"{res_pdf['gesamte_laufende_kosten_jahr']:,.0f} EUR",
            }
            pdf.chapter_body(sys_body)
        
        if not prognose_df_output.empty:
             pdf.add_plotly_fig(fig_prognose_output, title="Kostenprognose")


        # PDF zum Download anbieten
        pdf_output_bytes = pdf.output(dest='S').encode('latin-1') # Wichtig für Streamlit Download
        st.download_button(
            label="Bericht Herunterladen (PDF)",
            data=pdf_output_bytes,
            file_name=f"Energiebericht_{st.session_state.user_name}_{st.session_state.project_name}.pdf",
            mime="application/pdf"
        )
        st.success("PDF generiert. Klicken Sie auf den Button oben zum Herunterladen.")

# --- Footer ---
st.markdown("---")
st.caption(f"Stand der Annahmen und Berechnungen: {datetime.now().strftime('%d.%m.%Y %H:%M')}. Dies ist eine vereinfachte Modellrechnung.")
st.caption("Für eine detaillierte Planung sind Fachleute hinzuzuziehen. Kaleido muss für den vollen PDF-Grafikexport installiert sein.")