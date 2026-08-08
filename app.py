# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import os
import random
import re
import zipfile
import urllib.request
import shutil
import requests
from datetime import date
from openai import OpenAI

# --- 1. SÄTTER IKON OCH NAMN DIREKT I KÄRNAN ---
app_ikon = "icon.png" if os.path.exists("icon.png") else "💋"
st.set_page_config(layout="centered", page_title="6novl", page_icon=app_ikon)

# --- PWA / BOKMÄRKE-INSTÄLLNINGAR ---
components.html(
    """
    <script>
        const docHead = window.parent.document.head;
        
        const iconLink = window.parent.document.createElement('link');
        iconLink.rel = 'apple-touch-icon';
        iconLink.href = 'https://raw.githubusercontent.com/frinhosa/novlx/main/icon.png';
        docHead.appendChild(iconLink);
        
        const titleMeta = window.parent.document.createElement('meta');
        titleMeta.name = 'apple-mobile-web-app-title';
        titleMeta.content = '6novl';
        docHead.appendChild(titleMeta);
        
        const appCapable = window.parent.document.createElement('meta');
        appCapable.name = 'apple-mobile-web-app-capable';
        appCapable.content = 'yes';
        docHead.appendChild(appCapable);
    </script>
    """,
    height=0
)

# --- DESIGN & CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- INSTÄLLNINGAR ---
DEV_MODE = True
FILNAMN = "kategoriserade_berattelser.json"
ZIP_FILNAMN = "kategoriserade_berattelser.zip"
ZIP_URL = "https://github.com/frinhosa/novlx/releases/download/1.0/kategoriserade_berattelser.zip"
ANVANDAR_FIL = "anvandare.json"

# --- INNEHÅLLSFILTER ---
FORBJUDNA_ORD = [
    "minderårig", "minderåriga", "barn", "olaglig", "incest", 
    "våldtäkt", "våldtäkter", "pedofili", "djur", 
    "grova personangrepp", "trakasserier", "hot"
]

def ar_innehall_tillatet(prompt_text):
    text_att_testa = prompt_text.lower()
    for ord in FORBJUDNA_ORD:
        if re.search(r'\b' + re.escape(ord) + r'\b', text_att_testa):
            return False
    return True

# --- TELEGRAM NOTISER ---
def skicka_telegram_notis(ny_anvandare):
    try:
        if "TELEGRAM_BOT_TOKEN" in st.secrets and "TELEGRAM_CHAT_ID" in st.secrets:
            bot_token = st.secrets["TELEGRAM_BOT_TOKEN"]
            chat_id = st.secrets["TELEGRAM_CHAT_ID"]
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            meddelande = f"🚨 Ny användare registrerad i 6novl!\n\nAnvändarnamn: '{ny_anvandare}'"
            requests.post(url, json={"chat_id": chat_id, "text": meddelande})
    except Exception:
        pass

# --- DATABAS FÖR ANVÄNDARE (MED SJÄLV-REPARATION) ---
def ladda_anvandare():
    if not os.path.exists(ANVANDAR_FIL):
        data = {}
    else:
        with open(ANVANDAR_FIL, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = {}
                
    if "admin" not in data:
        data["admin"] = {"max_kvot": 100, "anvanda_idag": 0, "senaste_datum": str(date.today()), "godkand": True}
        
    if "admin" in data and "losenord" in data["admin"]:
        del data["admin"]["losenord"]
        
    if "admin" in data and "godkand" not in data["admin"]:
        data["admin"]["godkand"] = True
        
    with open(ANVANDAR_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data

def spara_anvandare(data):
    with open(ANVANDAR_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

anvandar_db = ladda_anvandare()

# --- INITIERA SESSION STATE ---
if "inloggad_anvandare" not in st.session_state:
    st.session_state.inloggad_anvandare = None

if "gast_genereringar" not in st.session_state:
    st.session_state.gast_genereringar = 0

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

aktiv_anvandare = st.session_state.inloggad_anvandare
dagens_datum = str(date.today())

# --- BERÄKNA KVOTER ---
if aktiv_anvandare:
    if anvandar_db[aktiv_anvandare].get("senaste_datum") != dagens_datum:
        anvandar_db[aktiv_anvandare]["anvanda_idag"] = 0
        anvandar_db[aktiv_anvandare]["senaste_datum"] = dagens_datum
        spara_anvandare(anvandar_db)

    anvanda_tokens = anvandar_db[aktiv_anvandare].get("anvanda_idag", 0)
    max_kvot = anvandar_db[aktiv_anvandare].get("max_kvot", 20)
else:
    anvanda_tokens = st.session_state.gast_genereringar
    max_kvot = 1  # Gäster får exakt 1 fri generering

# --- SIDOMENY OCH GÄST-INLOGG ---
with st.sidebar:
    if aktiv_anvandare:
        st.subheader(f"👤 {aktiv_anvandare.capitalize()}")
        st.progress(min(anvanda_tokens / max_kvot, 1.0))
        st.write(f"🎟️ Använda idag: {anvanda_tokens} av {max_kvot}")
        
        if aktiv_anvandare == "admin":
            st.markdown("---")
            st.subheader("🛠️ Hantera användare")
            befintliga_anvandare = [u for u in anvandar_db.keys() if u != "admin"]
            if befintliga_anvandare:
                anvandare_att_radera = st.selectbox("Radera användare:", ["Välj..."] + befintliga_anvandare)
                if anvandare_att_radera != "Välj..." and st.button(f"🗑️ Radera '{anvandare_att_radera}'"):
                    del anvandar_db[anvandare_att_radera]
                    spara_anvandare(anvandar_db)
                    st.rerun()
                    
        if st.button("Logga ut"):
            st.session_state.inloggad_anvandare = None
            st.rerun()
    else:
        st.subheader("👤 Gästläge")
        st.info("Du har 1 fri provgenerering. Skapa konto för full tillgång!")
        
        with st.expander("🔑 Logga in / Skapa konto"):
            tab1, tab2 = st.tabs(["Logga in", "Skapa konto"])
            with tab1:
                with st.form("sidebar_login_form"):
                    anvandarnamn = st.text_input("Användarnamn", key="sidebar_login_user").strip().lower()
                    losenord = st.text_input("Lösenord", type="password", key="sidebar_login_pass")
                    btn_login = st.form_submit_button("Logga in")
                    if btn_login:
                        if anvandarnamn == "admin":
                            if "ADMIN_PASSWORD" in st.secrets and losenord == st.secrets["ADMIN_PASSWORD"]:
                                st.session_state.inloggad_anvandare = "admin"
                                st.rerun()
                            else:
                                st.error("Fel lösenord.")
                        elif anvandarnamn in anvandar_db and anvandar_db[anvandarnamn].get("losenord") == losenord:
                            st.session_state.inloggad_anvandare = anvandarnamn
                            st.rerun()
                        else:
                            st.error("Fel användarnamn eller lösenord.")
            with tab2:
                with st.form("sidebar_reg_form"):
                    ny_anvandare = st.text_input("Välj användarnamn", key="sidebar_reg_user").strip().lower()
                    nytt_losenord = st.text_input("Välj lösenord", type="password", key="sidebar_reg_pass")
                    btn_reg = st.form_submit_button("Skapa konto")
                    if btn_reg:
                        if not ny_anvandare or not nytt_losenord:
                            st.warning("Fyll i alla fält.")
                        elif ny_anvandare in anvandar_db or ny_anvandare == "admin":
                            st.error("Användarnamnet är upptaget.")
                        else:
                            anvandar_db[ny_anvandare] = {
                                "losenord": nytt_losenord,
                                "max_kvot": 20,
                                "anvanda_idag": 0,
                                "senaste_datum": str(date.today()),
                                "godkand": True
                            }
                            spara_anvandare(anvandar_db)
                            skicka_telegram_notis(ny_anvandare)
                            st.session_state.inloggad_anvandare = ny_anvandare
                            st.rerun()

    st.markdown("---")
    st.caption("📧 Kontakt: 6novl@proton.me")

# --- API OCH DATABAS-LADDNING ---
api_key = None
try:
    if "OPENROUTER_API_KEY" in st.secrets:
        api_key = st.secrets["OPENROUTER_API_KEY"]
except Exception:
    pass

if not api_key and os.path.exists("openrouter_nyckel.txt"):
    with open("openrouter_nyckel.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()

if not api_key:
    st.error("Systemfel: Hittar inte API-nyckeln.")
    st.stop()

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

@st.cache_data
def ladda_och_parsa_fil():
    if not os.path.exists(FILNAMN):
        try:
            req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(ZIP_FILNAMN, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            with zipfile.ZipFile(ZIP_FILNAMN, 'r') as zip_ref:
                zip_ref.extractall(".")
        except Exception as e:
            raise Exception(f"Kunde inte ladda ner: {e}")
    if os.path.exists(FILNAMN):
        with open(FILNAMN, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

noveller = ladda_och_parsa_fil()

# --- UTVECKLARVERKTYG FÖR ADMIN ---
if DEV_MODE and aktiv_anvandare == "admin":
    with st.sidebar:
        st.subheader("🛠️ Utvecklarverktyg")
        st.info(f"Databas laddad: {len(noveller)} noveller")
        if "debug_info" in st.session_state:
            st.markdown("### 🎯 Matchning:")
            st.write(f"**Titel:** {st.session_state.debug_info['titel']}")
            st.write(f"**Poäng:** {st.session_state.debug_info['poang']}")
        if "senaste_referens" in st.session_state:
            st.caption("Utdrag till AI (Visar 150 tecken):")
            st.code(st.session_state.senaste_referens[:150] + "...", language="text")

# --- HUVUDYTA ---
st.title("6novl 💋")
st.markdown("<p style='font-style: italic; color: #888;'>Den interaktiva skrivarstudion för vuxenlitteratur.</p>", unsafe_allow_html=True)

# Ritar ut befintlig historia
for message in st.session_state.chat_history:
    ikon = "💋" if message["role"] == "assistant" else "🖋️"
    with st.chat_message(message["role"], avatar=ikon):
        st.write(message["content"])

# --- INMATNINGSLOGIK ---
user_input = None

# OM GÄSTEN HAR FÖRBRUKAT SIN 1 FRIA GENERERING -> VISA INLOGGNINGSMUR
if not aktiv_anvandare and st.session_state.gast_genereringar >= 1:
    st.warning("🔒 Du har provat din fria generering! Skapa ett gratis konto eller logga in för att fortsätta berättelsen (20 fria genereringar/dag).")
    
    t1, t2 = st.tabs(["Skapa konto (Snabbast)", "Logga in"])
    with t1:
        with st.form("main_reg_form"):
            u_reg = st.text_input("Användarnamn", key="main_reg_user").strip().lower()
            p_reg = st.text_input("Lösenord", type="password", key="main_reg_pass")
            main_reg_btn = st.form_submit_button("Skapa konto & Fortsätt 💋")
            if main_reg_btn:
                if not u_reg or not p_reg:
                    st.warning("Fyll i både användarnamn och lösenord.")
                elif u_reg in anvandar_db or u_reg == "admin":
                    st.error("Namnet är upptaget.")
                else:
                    anvandar_db[u_reg] = {
                        "losenord": p_reg,
                        "max_kvot": 20,
                        "anvanda_idag": 0,
                        "senaste_datum": str(date.today()),
                        "godkand": True
                    }
                    spara_anvandare(anvandar_db)
                    skicka_telegram_notis(u_reg)
                    st.session_state.inloggad_anvandare = u_reg
                    st.rerun()
    with t2:
        with st.form("main_log_form"):
            u_log = st.text_input("Användarnamn", key="main_log_user").strip().lower()
            p_log = st.text_input("Lösenord", type="password", key="main_log_pass")
            main_log_btn = st.form_submit_button("Logga in & Fortsätt")
            if main_log_btn:
                if u_log == "admin":
                    if "ADMIN_PASSWORD" in st.secrets and p_log == st.secrets["ADMIN_PASSWORD"]:
                        st.session_state.inloggad_anvandare = "admin"
                        st.rerun()
                    else:
                        st.error("Fel administratörslösenord.")
                elif u_log in anvandar_db and anvandar_db[u_log].get("losenord") == p_log:
                    st.session_state.inloggad_anvandare = u_log
                    st.rerun()
                else:
                    st.error("Fel användarnamn eller lösenord.")

# OM ANVÄNDAREN FÅR SKRIVA (GÄST MED 0 UTNYTTJAT ELLER INLOGGAD ANVÄNDARE)
else:
    if len(st.session_state.chat_history) == 0:
        with st.form(key="start_scen_form"):
            st.write("**Sätt scenen för din novell:**")
            user_input_raw = st.text_area(
                "Startscen", 
                placeholder="T.ex. Ett oväntat möte på tåget, en blick i en fullsatt bar, två kollegor som blir kvar sent på kontoret, eller spänningen i ett förbud...",
                height=130,
                label_visibility="collapsed"
            )
            skapa_knapp = st.form_submit_button("Börja berättelsen 💋")
            if skapa_knapp and user_input_raw.strip():
                user_input = user_input_raw.strip()
    else:
        placeholder = "Skriv 'mer' eller 'fortsätt' för att förlänga, eller styr handlingen fritt..."
        user_input = st.chat_input(placeholder)

# --- STIL-MATCHNINGS MOTOR ---
def hitta_stil_referens(user_prompt):
    if not noveller:
        return "", None
    try:
        stoppord = ["eller", "lite", "bara", "kanske", "också", "skriva", "gärna", "mycket", "något", "någon", "denna", "detta", "över", "vill", "till", "från", "inte", "utan", "vara"]
        sokord = [ord.lower() for ord in user_prompt.split() if len(ord) > 3 and ord.lower() not in stoppord]
        
        traffar = []
        for n in noveller:
            analys = n.get("analys", {})
            titel = n.get("title", "Okänd titel").lower()
            genre = (analys.get("genre", "") or "").lower()
            raw_tags = analys.get("tags")
            tags = [t.lower() for t in (raw_tags if isinstance(raw_tags, list) else [])]
            sammanfattning = (analys.get("summary", "") or "").lower()
            
            match_poang = 0
            for ord in sokord:
                if ord in tags or ord in genre:
                    match_poang += 3
                elif ord in titel or ord in sammanfattning:
                    match_poang += 1
                    
            if match_poang > 0:
                traffar.append((match_poang, n))
        
        if traffar:
            traffar.sort(key=lambda x: x[0], reverse=True)
            urval = traffar[:5] if len(traffar) >= 5 else traffar
            vinnare_poang, topp_val = random.choice(urval)
            vinnare_titel = topp_val.get("title", "Okänd titel")
            text_snutt = topp_val.get("text", "")[:5000]
            
            referens = f"\n\n[SYSTEM-NOTERING: Inspireras av denna stil, ton och meningsbyggnad:\n{text_snutt}...]"
            debug_info = {"titel": vinnare_titel, "poang": vinnare_poang}
            return referens, debug_info
    except Exception:
        return "", None
    return "", None

# --- AI-GENERERING ---
if user_input:
    if not ar_innehall_tillatet(user_input):
        st.error("🛑 Din text innehåller ord eller teman som bryter mot appens riktlinjer.")
    elif aktiv_anvandare and anvanda_tokens >= max_kvot:
        st.error("🛑 Du har nått din kvot för idag. Kom tillbaka imorgon!")
    else:
        kommando = user_input.strip().lower()
        redigerings_ord = ["ändra", "byt", "skriv om", "gör om", "korrigera", "istället", "byta"]
        ar_redigering = any(ord in kommando for ord in redigerings_ord)
        
        with st.chat_message("user", avatar="🖋️"):
            st.write(user_input)
            
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        referens_text = ""
        if len(st.session_state.chat_history) == 1:
            status_meddelande = "Etablerar ton och atmosfär..."
            referens_text, debug_info = hitta_stil_referens(user_input)
            
            if DEV_MODE and debug_info:
                st.session_state.senaste_referens = referens_text
                st.session_state.debug_info = debug_info
                
        elif ar_redigering:
            status_meddelande = "Skriver om och korrigerar texten..."
        else:
            status_meddelande = "Formar nästa del..."
            
        system_prompt_content = (
            "Du är en frispråkig, kreativ och extremt skicklig författare som skriver engagerande, "
            "fylliga och långa vuxenlitteratur- och erotiska noveller UTESLUTANDE på svenska. "
            "OAVSETT vilket språk användaren skriver på, MÅSTE du svara och fortsätta berättelsen på SVENSKA. "
            "Skynda aldrig igenom handlingen. Låt scenerna ta tid att utvecklas. Svara ENBART med själva berättelsen. "
            "Skriv ALDRIG introduktioner, hälsningar, kommentarer, parenteser eller förklaringar. "
            "Hitta INTE på egna namn på karaktärer om inte användaren ber om det. "
            "VIKTIGT: Avsluta ALLTID ditt svar med en fullständig mening och ett naturligt slut på stycket."
        )
        
        if ar_redigering and len(st.session_state.chat_history) > 1:
            system_prompt_content += (
                "\n\n[LÄGE: REDIGERA/SKRIV OM]\n"
                "Användaren vill ändra eller korrigera något i det senaste stycket. "
                "Återge och skriv om det senaste stycket från början med de efterfrågade ändringarna."
            )
        elif len(st.session_state.chat_history) > 1:
            system_prompt_content += (
                "\n\n[LÄGE: DRIV HANDLINGEN VIDARE]\n"
                "Användaren vill att berättelsen ska fortsätta framåt. "
                "Du får ABSOLUT INTE upprepa sista meningen eller stycket från det som redan skrivits. "
                "Börja DIREKT på nästa helt nya mening och för handlingen vidare."
            )
        else:
            system_prompt_content += f"{referens_text}"
            
        system_prompt = {"role": "system", "content": system_prompt_content}

        with st.chat_message("assistant", avatar="💋"):
            with st.spinner(status_meddelande):
                try:
                    response = client.chat.completions.create(
                        model="deepseek/deepseek-chat",
                        messages=[system_prompt] + st.session_state.chat_history,
                        max_tokens=4000,
                        temperature=0.9,
                        frequency_penalty=0.6,
                        presence_penalty=0.6
                    )
                    ai_response = response.choices[0].message.content
                    
                    if not ai_response.strip().endswith(('.', '!', '?', '"', '”', '…')):
                        senaste_avslut = max(ai_response.rfind('. '), ai_response.rfind('! '), ai_response.rfind('? '), ai_response.rfind('.”'))
                        if senaste_avslut != -1:
                            ai_response = ai_response[:senaste_avslut+1]
                    
                    st.write(ai_response)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    
                    # Uppdaterar förbrukning
                    if aktiv_anvandare:
                        anvandar_db[aktiv_anvandare]["anvanda_idag"] += 1
                        spara_anvandare(anvandar_db)
                    else:
                        st.session_state.gast_genereringar += 1
                    
                    st.session_state.scroll_to_ny = True 
                    st.rerun()
                    
                except Exception as e:
                    st.error("Ett fel uppstod vid genereringen. Försök igen.")

# --- MENYVAL: SPARA OCH STARTA OM ---
if len(st.session_state.chat_history) > 0:
    st.sidebar.markdown("---")
    komplett_berattelse = ""
    for meddelande in st.session_state.chat_history:
        if meddelande["role"] == "assistant":
            komplett_berattelse += meddelande["content"] + "\n\n"
            
    if komplett_berattelse.strip():
        st.sidebar.download_button(
            label="💾 Spara berättelsen",
            data=komplett_berattelse,
            file_name="min_6novl.txt",
            mime="text/plain"
        )
    
    if st.sidebar.button("🗑️ Starta en ny session"):
        st.session_state.chat_history = []
        st.session_state.gast_genereringar = 0
        
        if "senaste_referens" in st.session_state:
            del st.session_state.senaste_referens
        if "debug_info" in st.session_state:
            del st.session_state.debug_info
            
        st.rerun()

# --- AUTO-SCROLL ---
if st.session_state.get("scroll_to_ny", False):
    components.html(
        """
        <script>
            setTimeout(function() {
                const messages = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
                if (messages.length > 0) {
                    messages[messages.length - 1].scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            }, 500);
        </script>
        """,
        height=0
    )
    st.session_state.scroll_to_ny = False
