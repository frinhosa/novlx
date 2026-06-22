# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
import random
import re
import zipfile
import urllib.request
import shutil
from datetime import date
from openai import OpenAI

# Sätter en renare och mer minimalistisk sidlayout
st.set_page_config(layout="centered", page_title="6novl", page_icon="💋")

# --- INSTÄLLNINGAR ---
DEV_MODE = True
FILNAMN = "kategoriserade_berattelser.json"
ZIP_FILNAMN = "kategoriserade_berattelser.zip"
ZIP_URL = "https://github.com/frinhosa/novlx/releases/download/1.0/kategoriserade_berattelser.zip"
ANVANDAR_FIL = "anvandare.json"

# --- INNEHÅLLSFILTER (SVARTLISTA) ---
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

# --- 1. DATABAS FÖR ANVÄNDARE (MED SJÄLV-REPARATION) ---
def ladda_anvandare():
    if not os.path.exists(ANVANDAR_FIL):
        data = {}
    else:
        with open(ANVANDAR_FIL, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = {}
                
    # FIX: Återskapa admin om profilen saknas
    if "admin" not in data:
        data["admin"] = {"max_kvot": 100, "anvanda_idag": 0, "senaste_datum": str(date.today()), "godkand": True}
        
    # SÄKERHET: Radera gamla lösenord om de finns kvar
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

# --- 2. GATEKEEPER: INLOGGNING OCH REGISTRERING ---
if "inloggad_anvandare" not in st.session_state:
    st.session_state.inloggad_anvandare = None

if st.session_state.inloggad_anvandare is None:
    st.title("6novl 💋")
    st.write("Logga in eller skapa konto för att komma åt studion.")
    
    tab1, tab2 = st.tabs(["Logga in", "Skapa konto"])
    
    with tab1:
        anvandarnamn = st.text_input("Användarnamn", key="login_user").strip().lower()
        losenord = st.text_input("Lösenord", type="password", key="login_pass")
        if st.button("Logga in"):
            if anvandarnamn == "admin":
                if "ADMIN_PASSWORD" in st.secrets and losenord == st.secrets["ADMIN_PASSWORD"]:
                    st.session_state.inloggad_anvandare = "admin"
                    st.rerun()
                else:
                    st.error("Fel administratörslösenord.")
            elif anvandarnamn in anvandar_db and anvandar_db[anvandarnamn].get("losenord") == losenord:
                if anvandar_db[anvandarnamn].get("godkand", False):
                    st.session_state.inloggad_anvandare = anvandarnamn
                    st.rerun()
                else:
                    st.error("Ditt konto väntar fortfarande på godkännande av admin.")
            else:
                st.error("Fel användarnamn eller lösenord.")
                
    with tab2:
        ny_anvandare = st.text_input("Välj användarnamn", key="reg_user").strip().lower()
        nytt_losenord = st.text_input("Välj lösenord", type="password", key="reg_pass")
        if st.button("Skapa konto"):
            if not ny_anvandare or not nytt_losenord:
                st.warning("Fyll i både användarnamn och lösenord.")
            elif ny_anvandare == "admin" or ny_anvandare in anvandar_db:
                st.error("Användarnamnet är upptaget.")
            else:
                anvandar_db[ny_anvandare] = {
                    "losenord": nytt_losenord,
                    "max_kvot": 20,
                    "anvanda_idag": 0,
                    "senaste_datum": str(date.today()),
                    "godkand": False
                }
                spara_anvandare(anvandar_db)
                st.success("Konto skapat! Väntar på godkännande av admin.")
    st.stop()

aktiv_anvandare = st.session_state.inloggad_anvandare
dagens_datum = str(date.today())

if anvandar_db[aktiv_anvandare]["senaste_datum"] != dagens_datum:
    anvandar_db[aktiv_anvandare]["anvanda_idag"] = 0
    anvandar_db[aktiv_anvandare]["senaste_datum"] = dagens_datum
    spara_anvandare(anvandar_db)

anvanda_tokens = anvandar_db[aktiv_anvandare]["anvanda_idag"]
max_kvot = anvandar_db[aktiv_anvandare]["max_kvot"]

with st.sidebar:
    st.subheader(f"👤 {aktiv_anvandare.capitalize()}")
    if aktiv_anvandare == "admin":
        st.markdown("---")
        st.subheader("🛠️ Admin: Godkänn användare")
        pending_users = [u for u, data in anvandar_db.items() if not data.get("godkand", False)]
        if not pending_users:
            st.write("Inga väntande användare.")
        else:
            for user in pending_users:
                if st.button(f"Godkänn {user}"):
                    anvandar_db[user]["godkand"] = True
                    spara_anvandare(anvandar_db)
                    st.rerun()
    st.progress(min(anvanda_tokens / max_kvot, 1.0))
    st.write(f"🎟️ Använda generationer: {anvanda_tokens} av {max_kvot}")
    if st.button("Logga ut"):
        st.session_state.inloggad_anvandare = None
        st.session_state.chat_history = []
        st.rerun()
    st.markdown("---")
    st.caption("📧 Kontakt: 6novl@proton.me")

api_key = None
try:
    if "OPENROUTER_API_KEY" in st.secrets:
        api_key = st.secrets["OPENROUTER_API_KEY"]
except Exception:
    pass

if not api_key:
    if os.path.exists("openrouter_nyckel.txt"):
        with open("openrouter_nyckel.txt", "r", encoding="utf-8") as f:
            api_key = f.read().strip()
    else:
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
            raise Exception(f"Kunde inte ladda ner/packa upp: {e}")
    if os.path.exists(FILNAMN):
        with open(FILNAMN, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("Databas saknas.")

def ladda_bibliotek():
    try:
        return ladda_och_parsa_fil()
    except Exception as e:
        st.error(f"🚨 Databasfel: {e}")
        return []

noveller = ladda_bibliotek()
st.title("6novl 💋")
st.markdown("<p style='font-style: italic; color: #888;'>Den interaktiva skrivarstudion för vuxenlitteratur.</p>", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if DEV_MODE and aktiv_anvandare == "admin":
    with st.sidebar:
        st.subheader("🛠️ Utvecklarverktyg")
        st.info(f"Databas laddad: {len(noveller)} noveller")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = None
if len(st.session_state.chat_history) == 0:
    st.write("Beskriv en scen, en stämning eller en karaktär nedan för att påbörja berättelsen.")
    with st.form(key="start_scen_form"):
        user_input_raw = st.text_area("Vad vill du skriva om?", placeholder="Beskriv din vision...", height=150, label_visibility="collapsed")
        if st.form_submit_button("Påbörja berättelsen 💋") and user_input_raw.strip():
            user_input = user_input_raw.strip()
else:
    user_input = st.chat_input("Skriv 'mer' eller 'fortsätt' för att förlänga...")

def hitta_stil_referens(user_prompt):
    if not noveller: return "", None
    try:
        sokord = [ord.lower() for ord in user_prompt.split() if len(ord) > 3]
        traffar = []
        for n in noveller:
            metadata = f"{n.get('title', '')} {n.get('analys', {}).get('genre', '')}".lower()
            match_poang = sum(1 for ord in sokord if ord in metadata)
            if match_poang > 0: traffar.append((match_poang, n))
        if traffar:
            random.shuffle(traffar)
            traffar.sort(key=lambda x: x[0], reverse=True)
            topp_val = random.choice(traffar[:15])[1]
            return f"\n\n[SYSTEM: Inspireras av denna stil:\n{topp_val.get('text', '')[:2000]}...]", {"titel": topp_val.get("title")}
    except: return "", None
    return "", None

if user_input:
    if not ar_innehall_tillatet(user_input):
        st.error("🛑 Innehållet bryter mot riktlinjerna.")
    elif anvanda_tokens >= max_kvot:
        st.error("🛑 Gränsen nådd för idag.")
    else:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.write(user_input)
        
        system_prompt = "Du är en skicklig författare av vuxenlitteratur på svenska. Svara enbart med berättelsen."
        if len(st.session_state.chat_history) == 1:
            ref, _ = hitta_stil_referens(user_input)
            system_prompt += ref
        
        with st.chat_message("assistant"):
            with st.spinner("Formar texten..."):
                try:
                    response = client.chat.completions.create(model="deepseek/deepseek-chat", messages=[{"role": "system", "content": system_prompt}] + st.session_state.chat_history, max_tokens=4000)
                    ai_response = response.choices[0].message.content
                    st.write(ai_response)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    anvandar_db[aktiv_anvandare]["anvanda_idag"] += 1
                    spara_anvandare(anvandar_db)
                    st.rerun()
                except Exception as e: 
                    st.error("Ett fel uppstod vid genereringen. Försök igen.")

if st.sidebar.button("🗑️ Starta ny session"):
    st.session_state.chat_history = []
    st.rerun()
