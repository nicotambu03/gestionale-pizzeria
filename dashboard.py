import streamlit as st
import requests
import json
import qrcode
import os
import base64
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
from streamlit_autorefresh import st_autorefresh

# 1. CONFIGURAZIONE PAGINA (Deve essere tassativamente il primo comando Streamlit!)
st.set_page_config(page_title="Pizzeria Azzurra", page_icon="🍕", layout="wide", initial_sidebar_state="collapsed")

# 2. AVVIA L'AGGIORNAMENTO AUTOMATICO OGNI 5 SECONDI
st_autorefresh(interval=5000, key="data_refresh")
API_KEY = "jFm457qtsHn1_tSmKN1ceJldaCEV5nYsrxnspLsERgs"
GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
MATRIX_URL = "https://matrix.router.hereapi.com/v8/matrix"
TEMPO_CONSEGNA = 1

INDIRIZZO_PIZZERIA = "Via San Giovanni 7, Bovolone"
DB_FILE = "database_pizzeria.json"

PIZZE_INIZIALI = {
    "ANTO": 8.50, "ARCHIMEDE": 8.00, "AZZURRA": 8.00, "BOMBA": 8.00, "BOSCAIOLA": 7.50,
    "BRACCIO DI FERRO": 7.50, "BUFALINA": 7.50, "COLORATA": 8.00, "CALZONE": 8.00,
    "CARLO": 8.00, "CARMEN": 8.00, "CAPRICCIOSA": 8.00, "CONTADINA": 8.00,
    "CRUDO E BRIE": 8.50, "CRUDO E GORGONZOLA": 8.50, "CRUDO E MASCARPONE": 8.50,
    "CRUDO E RUCOLA": 8.00, "DAMIANO": 6.50, "DRUIDA": 8.50, "DUCHESSA": 8.00,
    "ERIK": 8.00, "ESTATE": 7.50, "FILIPPO": 8.00, "FRANCA": 8.00, "FRANCESCO": 8.00,
    "FRUTTI DI MARE": 8.50, "FUNGHI": 7.50, "GARRY": 7.50, "GIOVA": 8.00, "GIUGY": 8.00,
    "GORGONZOLA": 6.50, "ITALIA": 7.50, "LA NONNA": 8.00, "LUCIFERO": 8.00, "MARCO": 8.50,
    "MARGHERITA": 6.00, "MARINA": 6.50, "MARINARA": 6.00, "MANUELA": 8.00, "MASSIMO": 7.50,
    "MELANZANE": 7.50, "MONTE BIANCO": 8.00, "MORENO": 8.00, "NAPOLI": 6.50, "NEMO": 8.00,
    "PANCETTA AFFUMICATA": 7.00, "PANCETTA ARROTOLATA": 7.00, "PANCETTA E MASCARPONE": 8.00,
    "PANCETTA E MELINE": 8.00, "PAOLO": 7.50, "PATATE": 7.00, "PEPERON": 7.00, "PRIMAVERA": 8.00,
    "PROSCIUTTO": 7.00, "PROSCIUTTO E CARCIOFI": 7.50, "PROSCIUTTO E FUNGHI": 7.50, "ROMANA": 7.00,
    "RUOTA": 8.50, "RUSTICA": 7.50, "SALAMINO PICCANTE": 6.50, "SAPORITA": 8.00, "SICILIANA": 6.50,
    "SPECK E BRIE": 8.00, "SPECK E MASCARPONE": 8.00, "SPECK E RUCOLA": 8.00, "SPINACI E RICOTTA": 7.00,
    "SPINACI E SALSICCIA": 7.50, "STRAVAGANTE": 8.00, "TORNADO BLU": 8.50, "TOMMY": 8.00,
    "TONNO": 7.00, "TONNO E CIPOLLA": 7.50, "TRENTINA": 8.50, "TURTLES NINJA": 8.50,
    "VALENTINA": 8.00, "VEGETARIANA": 7.50, "VISITORS": 8.00, "WURSTEL": 7.00, "ZOE": 7.50,
    "ZUCCHINE": 7.00, "ZUKKY": 8.00, "4 FORMAGGI": 7.50, "4 STAGIONI": 8.00, "7 NANI": 19.50
}

AGGIUNTE_INIZIALI = {
    "Salamino piccante": 1.00, "Wurstel": 1.00, "Formaggi": 1.00, "Mozzarella di bufala": 2.50,
    "Crudo": 2.00, "Speck": 2.00, "Fantasia di funghi": 2.00, "Meline": 2.00
}


def carica_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            dati = json.load(f)
            if "menu_bevande" not in dati:
                dati["menu_bevande"] = {"Coca Cola 33cl": 2.50, "Acqua Naturale 1L": 1.50, "Birra 66cl": 3.50}
            if "incasso_sala" not in dati:
                dati["incasso_sala"] = 0.0
            if "pizze_sala_ritirate" not in dati:
                dati["pizze_sala_ritirate"] = 0
            if "menu_pizze" not in dati or len(dati["menu_pizze"]) < 10:
                dati["menu_pizze"] = PIZZE_INIZIALI
            if "menu_aggiunte" not in dati:
                dati["menu_aggiunte"] = AGGIUNTE_INIZIALI
            if "flotta" in dati:
                for k, v in dati["flotta"].items():
                    if "pizze_consegnate" not in v:
                        v["pizze_consegnate"] = 0
            return dati
    return {
        "turno_avviato": False, "NUM_CONSEGNATORI": 0, "ordini": [], "id_counter": 1,
        "giri_calcolati": {}, "flotta": {}, "incasso_sala": 0.0, "pizze_sala_ritirate": 0,
        "menu_pizze": PIZZE_INIZIALI, "menu_aggiunte": AGGIUNTE_INIZIALI,
        "menu_bevande": {"Coca Cola 33cl": 2.50, "Acqua Naturale 1L": 1.50, "Birra 66cl": 3.50}
    }


def salva_db(dati):
    with open(DB_FILE, "w") as f:
        json.dump(dati, f, indent=4)


# Forza la lettura in tempo reale del database per sincronizzare iPad e PC
db = carica_db()
st.session_state.db = db

if 'form_reset_key' not in st.session_state:
    st.session_state.form_reset_key = 0


def aggiungi_minuti_orario(orario_str, minuti):
    formato = "%H:%M"
    orario_dt = datetime.strptime(orario_str, formato)
    return (orario_dt + timedelta(minutes=minuti)).strftime(formato)


def ottieni_coordinate(indirizzo_testo):
    try:
        risposta = requests.get(GEOCODE_URL, params={"q": indirizzo_testo, "apiKey": API_KEY})
        dati = risposta.json()
        if dati.get("items") and len(dati["items"]) > 0:
            return dati["items"][0]["position"]["lat"], dati["items"][0]["position"]["lng"]
    except:
        pass
    return None, None


def genera_testo_scontrino(ordine):
    if ordine.get('is_sala', False):
        via_civico = "RITIRO IN SALA"
        paese = ""
    else:
        parti_indirizzo = ordine['indirizzo'].split(', ')
        via_civico = parti_indirizzo[0]
        paese = parti_indirizzo[1] if len(parti_indirizzo) > 1 else ""
    telefono_str = f"TEL: {ordine['telefono']}\n" if ordine.get('telefono') else ""
    testo = f"""
================================
        PIZZERIA AZZURRA
================================
Data: {datetime.now().strftime('%d/%m/%Y')}
Orario Consegna: {ordine['orario']}
--------------------------------
CLIENTE: {ordine['cognome']}
{telefono_str}VIA: {via_civico}
CITTA': {paese}
--------------------------------
ORDINE:
{ordine['dettaglio_gusti']}
--------------------------------
TOTALE: € {ordine['prezzo_totale']:.2f}
================================
"""
    return testo.strip()


def genera_testo_giro(risultato, orario):
    nome = risultato.get('id_giro', 'Giro')
    testo = f"""
================================
     {nome.upper()} DELLE {orario}
================================
TEMPO STIMATO: {risultato['route_time']} min
INCASSO TOTALE: € {risultato['incasso_giro']:.2f}
--------------------------------
TAPPE DA EFFETTUARE:
"""
    for tappa in risultato.get('dettagli_testo', []):
        testo += f"- {tappa}\n"
    testo += f"""
--------------------------------
LINK NAVIGATORE MAPS:
{risultato.get('qr_url', 'N/D')}
================================
"""
    return testo.strip()


def auto_download_file(testo, nome_file, ritardo_ms=0):
    b64 = base64.b64encode(testo.encode()).decode()
    identificatore = nome_file.replace(".", "_").replace(" ", "_")
    html = f"""
    <a id="dl_{identificatore}" href="data:text/plain;base64,{b64}" download="{nome_file}"></a>
    <script>
        setTimeout(function() {{
            document.getElementById('dl_{identificatore}').click();
        }}, {ritardo_ms});
    </script>
    """
    components.html(html, height=0)


orari_disponibili = [f"{h:02d}:{m:02d}" for h in range(18, 23) for m in (0, 15, 30, 45) if not (h == 22 and m > 0)]


def verifica_disponibilita(orario_scelto, nuove_pizze, num_cons, max_case, is_sala):
    MAX_PIZZE = 35
    MAX_ORDINI = num_cons * max_case

    ordini_slot_tutti = [o for o in db['ordini'] if o['orario'] == orario_scelto and not o.get('nascosto', False)]
    ordini_slot_consegne = [o for o in ordini_slot_tutti if not o.get('is_sala', False)]

    pizze_attuali = sum(o['pizze_totali'] for o in ordini_slot_tutti)
    consegne_attuali = len(ordini_slot_consegne)

    if pizze_attuali + nuove_pizze > MAX_PIZZE:
        return False, f"Forno pieno! (Già {pizze_attuali}/35 pizze alle {orario_scelto})"

    if not is_sala and consegne_attuali + 1 > MAX_ORDINI:
        return False, f"Fattorini occupati! (Già {consegne_attuali} consegne alle {orario_scelto})"

    return True, ""


def trova_alternative(nuove_pizze, num_cons, max_case, is_sala):
    alternative = []
    MAX_PIZZE = 35
    MAX_ORDINI = num_cons * max_case
    for o_time in orari_disponibili:
        ordini_slot_tutti = [o for o in db['ordini'] if o['orario'] == o_time and not o.get('nascosto', False)]
        ordini_slot_consegne = [o for o in ordini_slot_tutti if not o.get('is_sala', False)]

        pizze_attuali = sum(o['pizze_totali'] for o in ordini_slot_tutti)
        consegne_attuali = len(ordini_slot_consegne)

        if pizze_attuali + nuove_pizze <= MAX_PIZZE:
            if is_sala or (consegne_attuali + 1 <= MAX_ORDINI):
                alternative.append(o_time)
    return alternative


if not db.get('turno_avviato', False):
    st.title("🍕 Benvenuto! Configurazione Inizio Turno")
    st.markdown("---")

    g_sett = datetime.now().weekday()
    cons_suggeriti = 1 if g_sett <= 3 else (2 if g_sett == 4 else 4)

    col_setup1, col_setup2 = st.columns([1, 2])
    with col_setup1:
        st.subheader("🛵 Flotta di Stasera")
        num_cons = st.number_input("Quanti consegnatori lavorano stasera?", min_value=1, max_value=10,
                                   value=cons_suggeriti)

        with st.form("form_inizio_turno"):
            st.markdown("**Inserisci i nomi dei consegnatori presenti:**")
            nomi_inseriti = []
            for i in range(1, int(num_cons) + 1):
                nome_default = f"Ragazzo {i}"
                nomi_inseriti.append(st.text_input(f"Nome Consegnatore {i}", value=nome_default, key=f"nome_cons_{i}"))

            if st.form_submit_button("🚀 Avvia Turno", type="primary", use_container_width=True):
                db['NUM_CONSEGNATORI'] = int(num_cons)
                db['flotta'] = {}
                db['incasso_sala'] = 0.0
                db['pizze_sala_ritirate'] = 0
                for i in range(1, int(num_cons) + 1):
                    nome_scelto = nomi_inseriti[i - 1].strip().upper()
                    if not nome_scelto: nome_scelto = f"CONS. {i}"
                    db['flotta'][str(i)] = {
                        "id": str(i), "nome": nome_scelto, "occupato_fino_alle": "18:00",
                        "incasso_totale": 0.0, "storico_consegne": [], "pizze_consegnate": 0
                    }
                db['turno_avviato'] = True
                salva_db(db)
                st.rerun()

else:
    with st.sidebar:
        st.header("⚙️ Impostazioni Motore")
        MAX_TEMPO_GIRO = st.slider("Tempo max giro (minuti)", min_value=15, max_value=60, value=20, step=5)
        MAX_CASE_GIRO = st.slider("Max case per consegnatore", min_value=1, max_value=10, value=4, step=1)

    st.title(f"🍕 Dashboard Gestionale (Flotta: {db.get('NUM_CONSEGNATORI', 0)} 🛵)")
    st.markdown("---")

    tab_operativita, tab_cucina, tab_menu_view, tab_menu_edit, tab_cassa = st.tabs([
        "🚀 1. Cassa & Ordini",
        "👨‍🍳 2. Cucina",
        "📜 3. Menù Completo",
        "📝 4. Modifica Menù",
        "💰 5. Chiusura"
    ])

    with tab_operativita:
        col_inserimento, col_coda = st.columns([1, 2])

        with col_inserimento:
            st.subheader("📝 Nuovo Ordine")

            if "download_pending" in st.session_state:
                st.success(st.session_state.download_pending["msg"])
                auto_download_file(st.session_state.download_pending["text"],
                                   st.session_state.download_pending["filename"])
                del st.session_state.download_pending

            rk = st.session_state.form_reset_key

            numero_righe_pizze = st.number_input("Tipologie diverse di pizze?", min_value=1, max_value=20, value=1,
                                                 key=f"num_pizze_{rk}")
            numero_righe_bevande = st.number_input("Tipologie diverse di bevande (Opzionale)?", min_value=0,
                                                   max_value=10, value=0, key=f"num_bevande_{rk}")

            with st.form(f"form_nuovo_ordine_{rk}", clear_on_submit=False):
                st.markdown("### 🛒 Composizione Pizze")
                lista_dettagli_pizze = []

                for i in range(numero_righe_pizze):
                    st.markdown(f"**Pizza #{i + 1}**")
                    c_qta, c_formato = st.columns([1, 2])
                    with c_qta: qta = st.number_input("Q.tà", min_value=1, max_value=50, value=1, key=f"qta_p_{i}_{rk}")
                    with c_formato: formato = st.selectbox(
                        "Formato / Impasto",
                        ["Normale", "Baby (-€0.50)", "Doppia pasta altezza (+€2.00)", "Doppia pasta larghezza (€15.00)",
                         "Pizza metro (€22.00)", "Pizza famiglia (€22.00)", "Famiglia integrale (€24.00)"],
                        key=f"formato_p_{i}_{rk}"
                    )

                    gusti_scelti = st.multiselect("Gusti Pizza (Metro max 3, Famiglia max 4)",
                                                  list(db['menu_pizze'].keys()),
                                                  placeholder="Cerca i gusti desiderati...", key=f"gusti_p_{i}_{rk}")
                    aggiunte_scelte = st.multiselect("Aggiunte extra", list(db['menu_aggiunte'].keys()),
                                                     placeholder="Cerca aggiunte...", key=f"agg_p_{i}_{rk}")
                    modifiche = st.text_input("Note aggiuntive (es. -cipolla)", placeholder="es. ben cotta",
                                              key=f"mod_p_{i}_{rk}")
                    st.markdown("---")

                    lista_dettagli_pizze.append({
                        "quantita": qta,
                        "formato": formato,
                        "gusti": gusti_scelti,
                        "aggiunte": aggiunte_scelte,
                        "modifiche": modifiche
                    })

                lista_dettagli_bevande = []
                if numero_righe_bevande > 0:
                    st.markdown("### 🥤 Bevande Selezionate")
                    for i in range(numero_righe_bevande):
                        col_qtab, col_gustob = st.columns([1, 4])
                        with col_qtab: qtab = st.number_input("Q.tà", min_value=1, max_value=50, value=1,
                                                              key=f"qta_b_{i}_{rk}")
                        with col_gustob: gustob = st.selectbox("Bevanda", list(db['menu_bevande'].keys()), index=None,
                                                               placeholder="Cerca...", key=f"gusto_b_{i}_{rk}",
                                                               label_visibility="collapsed")
                        lista_dettagli_bevande.append({"quantita": qtab, "nome": gustob})

                st.markdown("---")
                is_sala = st.checkbox("🏠 Ritiro in Pizzeria (SALA)", value=False, key=f"is_sala_{rk}")

                col_via, col_civico = st.columns([3, 1])
                with col_via:
                    via = st.text_input("Via*", placeholder="es. Via Roma", disabled=is_sala, key=f"via_{rk}")
                with col_civico:
                    civico = st.text_input("Civico*", placeholder="es. 10", disabled=is_sala, key=f"civico_{rk}")
                paese = st.text_input("Paese", value="Bovolone", disabled=is_sala, key=f"paese_{rk}")

                col_orario, col_nome, col_tel = st.columns([2, 2, 2])
                with col_orario:
                    orario = st.selectbox("Orario Consegna/Ritiro", orari_disponibili, key=f"orario_{rk}")
                with col_nome:
                    cognome = st.text_input("Nome/Cognome*", placeholder="es. Rossi", key=f"cognome_{rk}")
                with col_tel:
                    telefono = st.text_input("Telefono (Opz.)", placeholder="es. 333", key=f"telefono_{rk}")

                if st.form_submit_button("➕ Aggiungi alla Coda (Stampa Automatica)"):
                    errore_compilazione = False
                    msg_errore = ""
                    for p in lista_dettagli_pizze:
                        num_g = len(p["gusti"])
                        form = p["formato"]

                        if "famiglia" in form.lower():
                            limit = 4
                        elif "metro" in form.lower():
                            limit = 3
                        else:
                            limit = 1

                        if num_g == 0:
                            errore_compilazione = True
                            msg_errore = "⚠️ Attenzione: devi selezionare almeno un gusto per ogni pizza!"
                        elif num_g > limit:
                            errore_compilazione = True
                            msg_errore = f"⚠️ Attenzione: il formato '{form}' supporta un massimo di {limit} gusti!"

                    if cognome.strip() == "":
                        st.error("⚠️ Il campo Nome/Cognome è obbligatorio!")
                    elif not is_sala and (via.strip() == "" or civico.strip() == "" or paese.strip() == ""):
                        st.error("⚠️ Compila i campi obbligatori (Via, Civico e Paese) per la consegna a domicilio!")
                    elif errore_compilazione:
                        st.error(msg_errore)
                    elif any(b['nome'] is None for b in lista_dettagli_bevande):
                        st.error("⚠️ Attenzione: devi selezionare il tipo per tutte le bevande!")
                    else:
                        prezzo_totale, pizze_totali_ordine = 0.0, 0
                        testo_riepilogo, testo_cucina = "", ""
                        indirizzo_completo = "SALA" if is_sala else f"{via.strip()} {civico.strip()}, {paese.strip()}"

                        for p in lista_dettagli_pizze:
                            prezzi_gusti = [db['menu_pizze'].get(g, 7.00) for g in p["gusti"]]
                            prezzo_base = max(prezzi_gusti) if prezzi_gusti else 7.00

                            extra_formato = 0.0
                            if "Baby" in p["formato"]:
                                prezzo_base -= 0.50
                            elif "altezza" in p["formato"]:
                                extra_formato = 2.00
                            elif "larghezza" in p["formato"]:
                                prezzo_base = 15.00
                            elif p["formato"] == "Pizza metro (€22.00)" or p["formato"] == "Pizza famiglia (€22.00)":
                                prezzo_base = 22.00
                            elif "integrale" in p["formato"].lower():
                                prezzo_base = 24.00

                            prezzo_aggiunte = sum(db['menu_aggiunte'].get(agg, 1.00) for agg in p["aggiunte"])
                            prezzo_riga = (prezzo_base + extra_formato + prezzo_aggiunte) * p['quantita']
                            prezzo_totale += prezzo_riga
                            pizze_totali_ordine += p['quantita']

                            str_gusti = " + ".join(p["gusti"])
                            str_formato = f" [{p['formato']}]" if "Normale" not in p["formato"] else ""
                            str_agg = f" (Agg: {', '.join(p['aggiunte'])})" if p["aggiunte"] else ""
                            str_note = f" Note: {p['modifiche']}" if p["modifiche"].strip() else ""

                            dett_base = f"{p['quantita']}x {str_gusti}{str_formato}{str_agg}{str_note}"

                            testo_cucina += f"🍕 {dett_base}\n"
                            testo_riepilogo += f"{dett_base} [€ {prezzo_riga:.2f}]\n"

                        for b in lista_dettagli_bevande:
                            prezzo_riga_b = db['menu_bevande'][b['nome']] * b['quantita']
                            prezzo_totale += prezzo_riga_b
                            dett_base_b = f"{b['quantita']}x {b['nome']}"
                            testo_cucina += f"🥤 {dett_base_b}\n"
                            testo_riepilogo += f"{dett_base_b} [€ {prezzo_riga_b:.2f}]\n"

                        if not is_sala and pizze_totali_ordine == 1:
                            if len(lista_dettagli_pizze) == 1 and "Normale" in lista_dettagli_pizze[0]["formato"]:
                                prezzo_totale += 1.00
                                testo_riepilogo += "🛵 Suppl. Consegna Singola [€ 1.00]\n"

                        is_valid, msg = verifica_disponibilita(orario, pizze_totali_ordine, db['NUM_CONSEGNATORI'],
                                                               MAX_CASE_GIRO, is_sala)

                        if not is_valid:
                            alt = trova_alternative(pizze_totali_ordine, db['NUM_CONSEGNATORI'], MAX_CASE_GIRO, is_sala)
                            alt_str = ", ".join(alt) if alt else "Nessun orario disponibile!"
                            st.error(f"❌ Impossibile inserire per le {orario}: {msg}")
                            st.warning(f"💡 **Orari alternativi consigliati:** {alt_str}")
                        else:
                            nuovo_ordine = {
                                "id": db['id_counter'], "cognome": cognome.upper(), "telefono": telefono.strip(),
                                "indirizzo": indirizzo_completo, "is_sala": is_sala,
                                "pizze_totali": pizze_totali_ordine,
                                "dettaglio_gusti": testo_riepilogo, "dettaglio_cucina": testo_cucina,
                                "orario": orario, "prezzo_totale": prezzo_totale, "nascosto": False
                            }
                            db['ordini'].append(nuovo_ordine)
                            db['id_counter'] += 1
                            if orario in db['giri_calcolati']: del db['giri_calcolati'][orario]
                            salva_db(db)

                            scontrino_txt = genera_testo_scontrino(nuovo_ordine)
                            st.session_state.download_pending = {
                                "text": scontrino_txt,
                                "filename": f"Scontrino_{cognome}_{orario.replace(':', '')}.txt",
                                "msg": f"✅ Ordine registrato e stampato per le {orario}!"
                            }

                            st.session_state.form_reset_key += 1
                            st.rerun()

        with col_coda:
            st.subheader("📋 Coda Ordini")
            ordini_attivi = [o for o in db['ordini'] if not o.get('nascosto', False)]

            ordini_consegna = [o for o in ordini_attivi if not o.get('is_sala', False)]
            ordini_sala = [o for o in ordini_attivi if o.get('is_sala', False)]

            tab_consegne, tab_sala = st.tabs(["🛵 Da Consegnare", "🏠 Ritiro in Sala"])

            with tab_consegne:
                if not ordini_consegna:
                    st.info("Nessuna consegna a domicilio in coda.")
                else:
                    for orario_blocco in sorted(list(set([o['orario'] for o in ordini_consegna]))):
                        st.markdown(f"### ⏰ Blocco Consegne delle {orario_blocco}")
                        ordini_blocco = [o for o in ordini_consegna if o['orario'] == orario_blocco]

                        for ordine in ordini_blocco:
                            col_info, col_print = st.columns([5, 1])
                            with col_info:
                                tel_display = f" 📞 {ordine['telefono']}" if ordine.get('telefono') else ""
                                st.write(
                                    f"- **{ordine['cognome']}**{tel_display}: {ordine['indirizzo']} 💶 **(€ {ordine['prezzo_totale']:.2f})**")
                            with col_print:
                                scontrino_txt = genera_testo_scontrino(ordine)
                                st.download_button(label="🔄 Ristampa", data=scontrino_txt,
                                                   file_name=f"Scontrino_{ordine['cognome']}_{ordine['orario'].replace(':', '')}.txt",
                                                   mime="text/plain", key=f"reprint_{ordine['id']}")

                        if orario_blocco in db['giri_calcolati']:
                            st.success(f"✅ Giri calcolati per le {orario_blocco}!")
                            risultati = db['giri_calcolati'][orario_blocco]
                            colonne = st.columns(len(risultati))

                            for idx, res in enumerate(risultati):
                                with colonne[idx]:
                                    nome_giro = res.get('id_giro', f"Giro {idx + 1}")
                                    st.info(f"🛵 {nome_giro}")
                                    st.write(
                                        f"⏱️ {res.get('route_time', 0)} min | 💶 € {res.get('incasso_giro', 0.0):.2f}")
                                    st.markdown("**📍 Tappe:**")
                                    for tappa in res.get('dettagli_testo', []): st.caption(f"- {tappa}")
                                    st.image(res.get('nome_file_qr', ''), width=120)

                                    lista_nomi_fattorini = [f"{c_id} - {d['nome']}" for c_id, d in db['flotta'].items()]
                                    scelta_fattorino = st.selectbox("Chi prende questo giro?", lista_nomi_fattorini,
                                                                    key=f"sel_cons_{orario_blocco}_{idx}")

                                    if st.button(f"🚀 FAI PARTIRE", key=f"partito_{orario_blocco}_{idx}",
                                                 type="primary"):
                                        c_id_scelto = scelta_fattorino.split(" - ")[0]

                                        if c_id_scelto in db['flotta']:
                                            db['flotta'][c_id_scelto]['incasso_totale'] += res.get('incasso_giro', 0.0)
                                            db['flotta'][c_id_scelto]['storico_consegne'].extend(
                                                res.get('dettagli_testo', []))
                                            db['flotta'][c_id_scelto]['pizze_consegnate'] = db['flotta'][
                                                                                                c_id_scelto].get(
                                                'pizze_consegnate', 0) + res.get('pizze_giro', 0)
                                            ora_partenza_effettiva = datetime.now()
                                            minuti_impiegati = res.get('route_time', 0) + 5
                                            orario_rientro = (ora_partenza_effettiva + timedelta(
                                                minutes=minuti_impiegati)).strftime("%H:%M")
                                            db['flotta'][c_id_scelto]['occupato_fino_alle'] = orario_rientro

                                        db['giri_calcolati'][orario_blocco].pop(idx)
                                        if len(db['giri_calcolati'][orario_blocco]) == 0:
                                            for o in db['ordini']:
                                                if o['orario'] == orario_blocco and not o.get('is_sala', False): o[
                                                    'nascosto'] = True
                                            del db['giri_calcolati'][orario_blocco]
                                        salva_db(db)
                                        st.rerun()
                        else:
                            if st.button(f"🚀 CALCOLA GIRI {orario_blocco} E STAMPA", key=f"btn_{orario_blocco}"):
                                with st.spinner('Calcolo e generazione riepiloghi in corso...'):
                                    lat_piz, lng_piz = ottieni_coordinate(INDIRIZZO_PIZZERIA)
                                    if not lat_piz: lat_piz, lng_piz = 45.2536, 11.1219
                                    coord_pizzeria = {"lat": lat_piz, "lng": lng_piz}
                                    punti_matrix = [coord_pizzeria]
                                    for ordine in ordini_blocco:
                                        lat, lon = ottieni_coordinate(ordine["indirizzo"])
                                        if lat and lon:
                                            punti_matrix.append({"lat": lat, "lng": lon})
                                        else:
                                            st.error(f"Indirizzo non trovato -> {ordine['indirizzo']}")

                                    payload = {"origins": punti_matrix, "destinations": punti_matrix,
                                               "regionDefinition": {"type": "world"},
                                               "matrixAttributes": ["travelTimes"]}
                                    risposta_matrice = requests.post(f"{MATRIX_URL}?apiKey={API_KEY}&async=false",
                                                                     headers={"Content-Type": "application/json"},
                                                                     data=json.dumps(payload))
                                    if risposta_matrice.status_code == 200:
                                        matrice_tempi = risposta_matrice.json()['matrix']['travelTimes']
                                        num_punti = len(punti_matrix)
                                        time_matrix = [
                                            [round(matrice_tempi[i * num_punti + j] / 60) for j in range(num_punti)] for
                                            i in range(num_punti)]
                                        num_veicoli = len(ordini_blocco)
                                        manager = pywrapcp.RoutingIndexManager(len(time_matrix), num_veicoli, 0)
                                        routing = pywrapcp.RoutingModel(manager)


                                        def time_callback(f, t):
                                            return time_matrix[manager.IndexToNode(f)][manager.IndexToNode(t)] + (
                                                TEMPO_CONSEGNA if manager.IndexToNode(t) != 0 else 0)


                                        transit_idx = routing.RegisterTransitCallback(time_callback)
                                        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)
                                        routing.AddDimension(transit_idx, 0, MAX_TEMPO_GIRO, True, 'Tempo')
                                        routing.SetFixedCostOfAllVehicles(10)


                                        def demand_callback(f):
                                            return 0 if manager.IndexToNode(f) == 0 else 1


                                        demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
                                        routing.AddDimension(demand_idx, 0, MAX_CASE_GIRO, True, 'Capacita')
                                        search_params = pywrapcp.DefaultRoutingSearchParameters()
                                        search_params.time_limit.seconds = 2
                                        solution = routing.SolveWithParameters(search_params)
                                        if solution:
                                            veicoli_utilizzati = sum(1 for v in range(num_veicoli) if not routing.IsEnd(
                                                solution.Value(routing.NextVar(routing.Start(v)))))
                                            if veicoli_utilizzati > db['NUM_CONSEGNATORI']:
                                                st.error(
                                                    f"❌ NON CI SONO ABBASTANZA CONSEGNATORI! Servono {veicoli_utilizzati} ragazzi per questo giro, ma la flotta totale è di {db['NUM_CONSEGNATORI']}.")
                                            else:
                                                risultati_blocco = []
                                                idx_cons = 1
                                                for vehicle_id in range(num_veicoli):
                                                    index = routing.Start(vehicle_id)
                                                    if routing.IsEnd(solution.Value(routing.NextVar(index))): continue
                                                    route_time, incasso_giro, pizze_giro = 0, 0.0, 0
                                                    coordinate_ordinate, dettagli_testo = [], []
                                                    while not routing.IsEnd(index):
                                                        node_index = manager.IndexToNode(index)
                                                        coordinate_ordinate.append(
                                                            f"{punti_matrix[node_index]['lat']},{punti_matrix[node_index]['lng']}")
                                                        if node_index != 0:
                                                            ordine = ordini_blocco[node_index - 1]
                                                            incasso_giro += ordine['prezzo_totale']
                                                            pizze_giro += ordine['pizze_totali']
                                                            tel_info = f" [📞 {ordine['telefono']}]" if ordine.get(
                                                                'telefono') else ""
                                                            dettagli_testo.append(
                                                                f"{ordine['indirizzo']}{tel_info} (€ {ordine['prezzo_totale']:.2f})")
                                                        prev_index = index
                                                        index = solution.Value(routing.NextVar(index))
                                                        route_time += time_matrix[manager.IndexToNode(prev_index)][
                                                                          manager.IndexToNode(index)] + (
                                                                          TEMPO_CONSEGNA if manager.IndexToNode(
                                                                              index) != 0 else 0)
                                                    node_index = manager.IndexToNode(index)
                                                    coordinate_ordinate.append(
                                                        f"{punti_matrix[node_index]['lat']},{punti_matrix[node_index]['lng']}")
                                                    qr_url = "https://www.google.com/maps/dir/" + "/".join(
                                                        coordinate_ordinate)
                                                    nome_file = f"qr_{orario_blocco.replace(':', '')}_v{vehicle_id}.png"
                                                    qrcode.make(qr_url).save(nome_file)

                                                    # LA RIGA CORRETTA DOVE HO INSERITO LE PIZZE GIRO AL SALVATAGGIO
                                                    risultati_blocco.append({
                                                        "id_giro": f"Giro {idx_cons}",
                                                        "route_time": route_time,
                                                        "incasso_giro": incasso_giro,
                                                        "dettagli_testo": dettagli_testo,
                                                        "nome_file_qr": nome_file,
                                                        "qr_url": qr_url,
                                                        "pizze_giro": pizze_giro
                                                    })
                                                    idx_cons += 1

                                                db['giri_calcolati'][orario_blocco] = risultati_blocco
                                                salva_db(db)
                                                for idx, res in enumerate(risultati_blocco):
                                                    txt_giro = genera_testo_giro(res, orario_blocco)
                                                    auto_download_file(txt_giro,
                                                                       f"{res['id_giro']}_{orario_blocco.replace(':', '')}.txt",
                                                                       ritardo_ms=(idx * 800))
                                        else:
                                            st.error(
                                                "❌ Impossibile rispettare i limiti. Aumenta il tempo max o riduci le case per giro.")

            with tab_sala:
                if not ordini_sala:
                    st.info("Nessun ordine in sala al momento.")
                else:
                    for orario_blocco in sorted(list(set([o['orario'] for o in ordini_sala]))):
                        st.markdown(f"### 🏠 Ritiro delle {orario_blocco}")
                        ordini_blocco = [o for o in ordini_sala if o['orario'] == orario_blocco]
                        for ordine in ordini_blocco:
                            with st.container(border=True):
                                col_info, col_print, col_done = st.columns([4, 1, 1])
                                with col_info:
                                    tel_display = f" 📞 {ordine['telefono']}" if ordine.get('telefono') else ""
                                    st.markdown(
                                        f"**{ordine['cognome']}**{tel_display} - 💶 **€ {ordine['prezzo_totale']:.2f}**")
                                with col_print:
                                    scontrino_txt = genera_testo_scontrino(ordine)
                                    st.download_button(label="🔄 Ristampa", data=scontrino_txt,
                                                       file_name=f"Scontrino_{ordine['cognome']}_{ordine['orario'].replace(':', '')}.txt",
                                                       mime="text/plain", key=f"reprint_sala_{ordine['id']}")
                                with col_done:
                                    if st.button("✅ Ritirato", key=f"sala_done_{ordine['id']}", type="primary"):
                                        db['incasso_sala'] += ordine['prezzo_totale']
                                        # AGGIUNTA LOGICA DELLE PIZZE SALA RITIRATE
                                        db['pizze_sala_ritirate'] = db.get('pizze_sala_ritirate', 0) + ordine[
                                            'pizze_totali']

                                        for o in db['ordini']:
                                            if o['id'] == ordine['id']: o['nascosto'] = True
                                        salva_db(db)
                                        st.rerun()

                st.markdown("---")
                st.markdown("#### ❌ Annulla Ordine")
                ordini_cancellabili = [o for o in db['ordini'] if not o.get('nascosto', False)]
                if ordini_cancellabili:
                    mappa_ordini = {o['id']: f"ID {o['id']} - {o['cognome']} (Ore {o['orario']})" for o in
                                    ordini_cancellabili}
                    col_canc1, col_canc2 = st.columns([3, 1])
                    with col_canc1:
                        ordine_da_canc = st.selectbox("Seleziona l'ordine da eliminare:",
                                                      options=list(mappa_ordini.keys()),
                                                      format_func=lambda x: mappa_ordini[x])
                    with col_canc2:
                        st.write("")
                        st.write("")
                        if st.button("🗑️ Elimina", type="primary"):
                            db['ordini'] = [o for o in db['ordini'] if o['id'] != ordine_da_canc]
                            orario_ordine = next(
                                (o['orario'] for o in ordini_cancellabili if o['id'] == ordine_da_canc), None)
                            if orario_ordine and orario_ordine in db['giri_calcolati']:
                                del db['giri_calcolati'][orario_ordine]
                            salva_db(db)
                            st.rerun()

    with tab_cucina:
        st.subheader("👨‍🍳 Comande Cucina")
        if HAS_AUTOREFRESH:
            auto_refresh = st.checkbox("🟢 Attiva Sincronizzazione Automatica (Solo se questo iPad sta fisso in cucina)",
                                       value=False)
            if auto_refresh:
                st_autorefresh(interval=5000, key="cucina_refresh")
                st.caption("Aggiornamento attivo ogni 5 secondi...")
        else:
            st.error("⚠️ Modulo 'streamlit-autorefresh' non installato.")
            if st.button("🔄 Aggiorna Comande Manualmente", use_container_width=True): st.rerun()

        st.markdown("---")
        ordini_attivi = [o for o in db['ordini'] if not o.get('nascosto', False)]

        if not ordini_attivi:
            st.info("Nessuna consegna in coda. La cucina riposa! 🍕")
        else:
            for orario_blocco in sorted(list(set([o['orario'] for o in ordini_attivi]))):
                ordini_blocco = [o for o in ordini_attivi if o['orario'] == orario_blocco]
                totale_pizze = sum(o['pizze_totali'] for o in ordini_blocco)

                st.markdown(
                    f"<h3 style='text-align: center; color: white; background-color: #d9534f; padding: 10px; border-radius: 5px;'>⏰ INFORNATA DELLE {orario_blocco} - TOTALE: {totale_pizze} PIZZE</h3>",
                    unsafe_allow_html=True)

                colonne_cucina = st.columns(3)
                for idx, ordine in enumerate(ordini_blocco):
                    with colonne_cucina[idx % 3]:
                        with st.container(border=True):
                            indirizzo_display = "🏠 SALA" if ordine.get('is_sala', False) else ordine['indirizzo']
                            st.markdown(f"**{ordine['cognome']}**<br><small>{indirizzo_display}</small>",
                                        unsafe_allow_html=True)
                            st.markdown("---")
                            for riga_pizza in ordine['dettaglio_cucina'].strip().split('\n'):
                                if riga_pizza: st.write(f"**{riga_pizza}**")
                st.write("")

    with tab_menu_view:
        st.subheader("📜 Menù Completo")
        col_vp, col_va, col_vb = st.columns(3)
        with col_vp:
            st.markdown("### 🍕 Pizze")
            st.dataframe(
                {"Pizza": list(db['menu_pizze'].keys()), "Prezzo": [f"€ {v:.2f}" for v in db['menu_pizze'].values()]},
                hide_index=True, use_container_width=True)
        with col_va:
            st.markdown("### ➕ Aggiunte")
            st.dataframe({"Aggiunta": list(db['menu_aggiunte'].keys()),
                          "Prezzo": [f"€ {v:.2f}" for v in db['menu_aggiunte'].values()]}, hide_index=True,
                         use_container_width=True)
        with col_vb:
            st.markdown("### 🥤 Bevande")
            st.dataframe({"Bevanda": list(db['menu_bevande'].keys()),
                          "Prezzo": [f"€ {v:.2f}" for v in db['menu_bevande'].values()]}, hide_index=True,
                         use_container_width=True)

    with tab_menu_edit:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.subheader("🍕 Modifica Pizze")
            with st.form("form_aggiungi_pizza_edit"):
                nuovo_gusto = st.text_input("Nome Pizza")
                nuovo_prezzo = st.number_input("Prezzo (€)", min_value=1.00, value=8.00, step=0.50)
                if st.form_submit_button("Aggiungi Pizza", use_container_width=True):
                    if nuovo_gusto.strip() and nuovo_gusto.strip().upper() not in db['menu_pizze']:
                        db['menu_pizze'][nuovo_gusto.strip().upper()] = nuovo_prezzo
                        salva_db(db)
                        st.session_state.db = db
                        st.success("Aggiunta!")
                        st.rerun()
            if db['menu_pizze']:
                gusto_mod = st.selectbox("Modifica/Elimina Pizza", list(db['menu_pizze'].keys()))
                prezzo_mod = st.number_input("Prezzo (€)", min_value=1.00, value=float(db['menu_pizze'][gusto_mod]),
                                             step=0.50, key="p_Mod")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔄 Aggiorna", use_container_width=True):
                        db['menu_pizze'][gusto_mod] = prezzo_mod
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()
                with c2:
                    if st.button("🗑️ Elimina", use_container_width=True) and gusto_mod != "MARGHERITA":
                        del db['menu_pizze'][gusto_mod]
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()
        with col_m2:
            st.subheader("➕ Modifica Aggiunte")
            with st.form("form_aggiungi_agg_edit"):
                nuova_agg = st.text_input("Nome Aggiunta")
                prezzo_agg = st.number_input("Prezzo (€)", min_value=0.50, value=1.50, step=0.50)
                if st.form_submit_button("Aggiungi Extra", use_container_width=True):
                    if nuova_agg.strip() and nuova_agg.strip() not in db['menu_aggiunte']:
                        db['menu_aggiunte'][nuova_agg.strip()] = prezzo_agg
                        salva_db(db)
                        st.session_state.db = db
                        st.success("Aggiunta!")
                        st.rerun()
            if db['menu_aggiunte']:
                agg_mod = st.selectbox("Modifica/Elimina Aggiunta", list(db['menu_aggiunte'].keys()))
                prezzo_amod = st.number_input("Prezzo Extra (€)", min_value=0.50,
                                              value=float(db['menu_aggiunte'][agg_mod]), step=0.50, key="a_Mod")
                c1a, c2a = st.columns(2)
                with c1a:
                    if st.button("🔄 Aggiorna Aggiunta", use_container_width=True):
                        db['menu_aggiunte'][agg_mod] = prezzo_amod
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()
                with c2a:
                    if st.button("🗑️ Elimina Aggiunta", use_container_width=True):
                        del db['menu_aggiunte'][agg_mod]
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()
        with col_m3:
            st.subheader("🥤 Modifica Bevande")
            with st.form("form_aggiungi_bevanda_edit"):
                nuovo_gusto_b = st.text_input("Nome Bevanda")
                nuovo_prezzo_b = st.number_input("Prezzo (€)", min_value=0.50, value=2.50, step=0.50)
                if st.form_submit_button("Aggiungi Bevanda", use_container_width=True):
                    if nuovo_gusto_b.strip() and nuovo_gusto_b.strip() not in db['menu_bevande']:
                        db['menu_bevande'][nuovo_gusto_b.strip()] = nuovo_prezzo_b
                        salva_db(db)
                        st.session_state.db = db
                        st.success("Aggiunta!")
                        st.rerun()
            if db['menu_bevande']:
                gusto_mod_b = st.selectbox("Modifica/Elimina Bevanda", list(db['menu_bevande'].keys()))
                prezzo_mod_b = st.number_input("Prezzo (€)", min_value=0.50,
                                               value=float(db['menu_bevande'][gusto_mod_b]), step=0.50, key="b_Mod")
                c1b, c2b = st.columns(2)
                with c1b:
                    if st.button("🔄 Aggiorna Bevanda", use_container_width=True):
                        db['menu_bevande'][gusto_mod_b] = prezzo_mod_b
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()
                with c2b:
                    if st.button("🗑️ Elimina Bevanda", use_container_width=True):
                        del db['menu_bevande'][gusto_mod_b]
                        salva_db(db)
                        st.session_state.db = db
                        st.rerun()

    with tab_cassa:
        st.subheader("💰 Resoconto Serata")

        incasso_sala = db.get("incasso_sala", 0.0)
        incasso_fattorini = sum(d.get('incasso_totale', 0.0) for d in db['flotta'].values())
        incasso_totale = incasso_sala + incasso_fattorini

        # NUOVO CONTEGGIO PIZZE CHIARO E DIVISO
        pizze_domicilio = sum(d.get('pizze_consegnate', 0) for d in db['flotta'].values())
        pizze_sala = db.get("pizze_sala_ritirate", 0)
        pizze_totali_serata = pizze_domicilio + pizze_sala

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🛵 Incasso Fattorini", f"€ {incasso_fattorini:.2f}")
        c2.metric("🏠 Incasso Sala", f"€ {incasso_sala:.2f}")
        c3.metric("💶 TOTALE SERATA", f"€ {incasso_totale:.2f}")
        c4.metric("🛵 Pizze Domicilio", f"{pizze_domicilio}")
        c5.metric("🏠 Pizze Sala", f"{pizze_sala}")

        st.markdown("---")
        st.markdown("### Dettaglio Fattorini")
        colonne_cassa = st.columns(min(4, max(1, db.get('NUM_CONSEGNATORI', 1))))

        for i, (c_id, dati) in enumerate(db['flotta'].items()):
            with colonne_cassa[i % len(colonne_cassa)]:
                with st.container(border=True):
                    nome_display = dati.get('nome', f"CONS. {c_id}")
                    st.markdown(f"### 🛵 {nome_display}")
                    st.metric(label="In cassa", value=f"€ {dati.get('incasso_totale', 0.0):.2f}")

                    num_consegne = len(dati.get('storico_consegne', []))
                    pizze_cons = dati.get('pizze_consegnate', 0)

                    st.markdown(f"**📦 Consegne fatte:** {num_consegne}")
                    st.markdown(f"**🍕 Pizze portate:** {pizze_cons}")

                    if dati.get('occupato_fino_alle', '18:00') != "18:00":
                        st.caption(f"Ultimo rientro stimato: {dati['occupato_fino_alle']}")
                    st.markdown("**Storico Vie:**")
                    if not dati.get('storico_consegne'):
                        st.write("*Nessuna.*")
                    else:
                        for via in dati['storico_consegne']: st.write(f"- {via}")

        st.markdown("---")
        if st.button("🗑️ Termina Serata e Azzera Tutto", type="primary"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.session_state.clear()
            st.rerun()
