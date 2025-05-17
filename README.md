# Energiebedarfsanalyse Mehrfamilienhaus (Streamlit App)

Diese Streamlit-Anwendung dient zur detaillierten Kosten- und Energiebedarfsanalyse für Mehrfamilienhäuser. Sie ermöglicht die Eingabe von Gebäudedaten, die Berechnung des Heizwärmebedarfs, die Integration einer PV-Anlage, den Vergleich verschiedener Heizsysteme und eine Kostenprognose.

## Hauptfunktionen

* **Gebäudeparameter:**
    * Eingabe von Baujahr, Flächen (Außenwände, Dach, Boden, Fenster).
    * U-Wert-Vorschläge basierend auf Baujahr und Dämmstandards (WDVS etc.).
    * Berücksichtigung von ungedämmten Außenwandanteilen.
    * Berechnung des Transmissionswärmeverlustkoeffizienten ($H_T$).
* **Bedarfsberechnung:**
    * Nutzung eines Referenz-Temperaturprofils für Deutschland.
    * Berechnung des jährlichen und monatlichen Heizwärmebedarfs.
    * Eingabe von Personenzahl und Energiesparfaktor zur Ermittlung des Brauchwasser- und Haushaltsstrombedarfs (mit manueller Korrekturmöglichkeit für Haushaltsstrom).
* **PV-Anlage:**
    * Konfiguration von Anlagengröße (kWp), Ausrichtung, Neigung und optional Batteriespeicher.
    * Auswahl verschiedener PV-Strom-Nutzungsstrategien.
    * Berechnung des monatlichen PV-Ertrags.
* **Heizsystemvergleich:**
    * Vergleich von Gasheizung, Wärmepumpe (Luft-Wasser) und Fernwärme.
    * Anpassbare Investitions- und Wartungskosten (auch für PV-Anlage separat).
    * Berechnung der jährlichen laufenden Kosten (Energie, Wartung).
* **Visualisierung:**
    * Grafische Darstellung des Temperaturprofils.
    * Monatliche Energiebilanz (Bedarfe vs. PV-Erzeugung).
    * Typischer Tagesverlauf der Energieflüsse für einen ausgewählten Monat.
    * Grafische Darstellung der Kostenprognose über 15 Jahre.
* **Projektmanagement & Export:**
    * Speichern und Laden von Projektkonfigurationen als `.json`-Datei (benutzer-/projektnamenbasiert).
    * Export der wichtigsten Ergebnisse und Grafiken als PDF-Bericht.

## Setup & Installation

1.  **Voraussetzungen:**
    * Python 3.8 oder neuer.
    * Git (optional, für das Klonen des Repositories).

2.  **Umgebung einrichten (Empfohlen):**
    Erstellen Sie eine virtuelle Umgebung und aktivieren Sie diese:
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Abhängigkeiten installieren:**
    Installieren Sie die benötigten Python-Pakete:
    ```bash
    pip install -r requirements.txt
    ```
    **Hinweis zu Kaleido:** Für den Export von Grafiken im PDF-Bericht wird `kaleido` benötigt. Die Installation kann je nach System zusätzliche Schritte erfordern. Falls Probleme auftreten, konsultieren Sie bitte die offizielle Dokumentation von Plotly und Kaleido.

## Anwendung starten

Führen Sie die Streamlit-Anwendung mit folgendem Befehl aus (ersetzen Sie `your_app_script_name.py` mit dem tatsächlichen Namen Ihrer Python-Datei):

```bash
streamlit run your_app_script_name.py