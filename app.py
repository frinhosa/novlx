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

# Sätter en renare och mer minimalistisk sidlayout
st.set_page_config(layout="centered", page_title="6novl", page_icon="💋")

# --- DESIGN & CSS (DÖLJER STANDARD-GRAFIK) ---
st.markdown("""
    <style>
    /* Döljer Streamlits hamburgermeny */
    #MainMenu {visibility: hidden;}
    /* Döljer headern */
    header {visibility: hidden;}
    /* Döljer 'Made with Streamlit' i botten */
    footer {visibility: hidden;}
    /* Döljer den animerade gubben/status-widgeten */
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

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

# --- TELEGRAM NOTISER ---
def skicka_telegram_notis(ny_anvandare):
    try:
        if "TELEGRAM_BOT_TOKEN" in st.secrets and "TELEGRAM_CHAT_ID" in st.secrets:
            bot_token = st.secrets["TELEGRAM_BOT_TOKEN"]
            chat_id = st.secrets["TELEGRAM_CHAT_ID"]
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            meddelande = f"🚨 Ny användare i 6novl!\n\nAnvändarnamn: '{ny_anvandare}' väntar på ditt godkännande."
            
            requests.post(url, json={"chat_id": chat_id, "text": meddelande})
    except Exception:
        pass

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

# --- 2. GATEKEEPER: INLOGGNING OCH REGISTRERING ---
if "inloggad_anvandare" not in st.session_state:
    st.session_state.inloggad_anvandare = None

if st.session_state.inloggad_anvandare is None:
    st.title("6novl 💋")
    st.write("Logga in eller skapa konto för att komma åt studion.")
    
    tab1, tab2 = st.tabs(["
