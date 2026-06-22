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
st.set_page_config(layout="centered", page_title="novlx", page_icon="💋")

# --- INSTÄLLNINGAR ---
DEV_MODE = True
FILNAMN = "kategoriserade_berattelser.json"
ZIP_FILNAMN = "kategoriserade_berattelser.zip"
ZIP_URL = "https://github.com/frinhosa/novlx/releases/download/1.0/kategoriserade_berattelser.zip"
ANVANDAR_FIL = "anvandare.json"

# --- 1. DATABAS FÖR ANVÄNDARE (MED SJÄLV-REPARATION) ---
def ladda_anvandare():
    if not os.path.exists(ANVANDAR_FIL):
        data = {
            "admin": {"losenord": "novlx2026", "max_kvot": 100, "anvanda_idag": 0, "senaste_datum": str(date.today()), "godkand": True}
        }
    else:
        with open(ANVANDAR_FIL, "r", encoding="utf-8") as f:
            data = json.load(f)
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
    st.title("novlx 💋")
    st.write("Logga in eller skapa konto för att komma åt studion.")
    
    tab1, tab2 = st.tabs(["Logga in", "Skapa konto"])
    
    with tab1:
        anvandarnamn = st.text_input("Användarnamn", key="login_user").strip().lower()
        losenord = st.text_input("Lösenord", type="password", key="login_pass")
        if st.button("Logga in"):
            if anvandarnamn in anvandar_db and anvandar_db[anvandarnamn]["losenord"] == losenord:
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
            if ny_anvandare in anvandar_db:
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

# --- 3. ANVÄNDAREN ÄR INLOGGAD ---
aktiv_anvandare = st.session_state.inloggad_anvandare
dagens_datum = str(date.today())

if anvandar_db[aktiv_anvandare]["senaste_datum"] != dagens_datum:
    anvandar_db[aktiv_anvandare]["anvanda_idag"] = 0
    anvandar_db[aktiv_anvandare]["senaste_datum"] = dagens_datum
    spara_anvandare(anvandar_db)

anvanda_tokens = anvandar_db[aktiv_anvandare]["anvanda_idag"]
max_kvot = anvandar_db[aktiv_anvandare]["max_kvot"]

# --- 4. ADMINISTRATÖR & SIDOMENY ---
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

# --- 5. SMART NERLADDNING (GITHUB RELEASES) ---
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

noveller = ladda_och_parsa_fil()

# --- 6. CHATT OCH LOGIK ---
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=st.secrets.get("OPENROUTER_API_KEY"))

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("novlx 💋")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = st.chat_input("Beskriv din vision...")

if user_input:
    if anvanda_tokens >= max_kvot:
        st.error("Kvot slut.")
    else:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
            
        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    model="deepseek/deepseek-chat",
                    messages=[{"role": "system", "content": "Skriv en engagerande novell."}] + st.session_state.chat_history,
                )
                ai_response = response.choices[0].message.content
                st.write(ai_response)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                anvandar_db[aktiv_anvandare]["anvanda_idag"] += 1
                spara_anvandare(anvandar_db)
                st.rerun()
            except Exception as e:
                st.error(f"Fel: {e}")
