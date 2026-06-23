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
                skicka_telegram_notis(ny_anvandare)
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
    st.markdown("---")
    st.caption("📧 Kontakt: 6novl@proton.me")

# --- KAMELEON-LÖSNING FÖR API-NYCKEL ---
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

# --- 5. SMART NERLADDNING ---
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

# --- 6. DESIGN: HUVUDAPPEN ---
st.title("6novl 💋")
st.markdown("<p style='font-style: italic; color: #888;'>Den interaktiva skrivarstudion för vuxenlitteratur.</p>", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

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

# --- RITAR UT HISTORIKEN (MED NYA AVATARER) ---
for message in st.session_state.chat_history:
    ikon = "💋" if message["role"] == "assistant" else "🖋️"
    with st.chat_message(message["role"], avatar=ikon):
        st.write(message["content"])

# --- DYNAMISKT TEXTFÄLT (FLIPP-FLOPP) ---
user_input = None

if len(st.session_state.chat_history) == 0:
    st.write("Beskriv en scen, en stämning eller en karaktär nedan för att påbörja berättelsen.")
    with st.form(key="start_scen_form"):
        user_input_raw = st.text_area(
            "Vad vill du skriva om?", 
            placeholder="Beskriv din vision (t.ex. 'Ett intensivt och oväntat möte i ett regnigt Stockholm')...",
            height=150,
            label_visibility="collapsed"
        )
        skapa_knapp = st.form_submit_button("Påbörja berättelsen 💋")
        if skapa_knapp and user_input_raw.strip():
            user_input = user_input_raw.strip()
else:
    placeholder = "Skriv 'mer' eller 'fortsätt' för att förlänga, eller styr handlingen fritt..."
    user_input = st.chat_input(placeholder)

# --- DEN NYA UPPDATERADE STIL-MATCHNINGS MOTORN ---
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
                # Viktad sökning: Taggar och genre ger 3 poäng, titel och sammanfattning ger 1 poäng
                if ord in tags or ord in genre:
                    match_poang += 3
                elif ord in titel or ord in sammanfattning:
                    match_poang += 1
                    
            if match_poang > 0:
                traffar.append((match_poang, n))
        
        if traffar:
            # Sorterar så den högsta poängen ligger först
            traffar.sort(key=lambda x: x[0], reverse=True)
            
            # Väljer bland de 5 absolut bästa träffarna istället för de 15 bästa
            urval = traffar[:5] if len(traffar) >= 5 else traffar
            vinnare_poang, topp_val = random.choice(urval)
            vinnare_titel = topp_val.get("title", "Okänd titel")
            
            # Utökat kontext till 5000 tecken för mycket djupare stil-förståelse
            text_snutt = topp_val.get("text", "")[:5000]
            
            referens = f"\n\n[SYSTEM-NOTERING: Inspireras av denna stil, ton och meningsbyggnad:\n{text_snutt}...]"
            debug_info = {"titel": vinnare_titel, "poang": vinnare_poang}
            return referens, debug_info
    except Exception:
        return "", None
    return "", None

# --- GENERERINGS-LOGIK (UPPSTRAMAD PROMPT) ---
if user_input:
    if not ar_innehall_tillatet(user_input):
        st.error("🛑 Din text innehåller ord eller teman som bryter mot appens riktlinjer. Vänligen justera din beskrivning.")
    elif anvanda_tokens >= max_kvot:
        st.error("🛑 Du har nått din gräns för skapande idag. Kom tillbaka imorgon!")
    else:
        kommando = user_input.strip().lower()
        ar_fortsattning = kommando in ["fortsätt", "mer", "vidare", ".", "..", "..."] and len(st.session_state.chat_history) > 0
        
        with st.chat_message("user", avatar="🖋️"):
            st.write(user_input)
            
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        referens_text = ""
        status_meddelande = "Formar nästa del..." if ar_fortsattning else "Formar texten..."
        
        if len(st.session_state.chat_history) == 1:
            status_meddelande = "Etablerar ton och atmosfär..."
            referens_text, debug_info = hitta_stil_referens(user_input)
            if DEV_MODE and debug_info:
                st.session_state.senaste_referens = referens_text
                st.session_state.debug_info = debug_info
            
        system_prompt_content = (
            "Du är en frispråkig, kreativ och extremt skicklig författare som skriver engagerande, "
            "fylliga och långa vuxenlitteratur- och erotiska noveller på svenska. "
            "Skynda aldrig igenom handlingen. Låt scenerna ta tid att utvecklas. Svara enbart med berättelsen. "
            "Hitta INTE på egna namn på karaktärer om inte användaren ber om det eller nämner dem. "
            "VIKTIGT: Avsluta ALLTID ditt svar med en fullständig mening och ett naturligt slut på stycket, oavsett hur lång texten blir."
        )
        
        if ar_fortsattning:
            system_prompt_content += "\n\n[VIKTIGT: Driv handlingen FRAMÅT från allra sista meningen. Upprepa INTE och skriv INTE om det du redan skrivit. Jag vill enbart ha NÄSTA händelseförlopp i berättelsen.]"
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
                        temperature=0.9
                    )
                    ai_response = response.choices[0].message.content
                    
                    if not ai_response.strip().endswith(('.', '!', '?', '"', '”', '…')):
                        senaste_avslut = max(ai_response.rfind('. '), ai_response.rfind('! '), ai_response.rfind('? '), ai_response.rfind('.”'))
                        if senaste_avslut != -1:
                            ai_response = ai_response[:senaste_avslut+1]
                    
                    st.write(ai_response)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    anvandar_db[aktiv_anvandare]["anvanda_idag"] += 1
                    spara_anvandare(anvandar_db)
                    
                    # --- AKTIVERAR AUTO-SCROLL ---
                    st.session_state.scroll_to_ny = True 
                    st.rerun()
                    
                except Exception as e:
                    if DEV_MODE:
                        st.error(f"API-fel: {e}")
                    else:
                        st.error("Ett fel uppstod vid genereringen. Försök igen.")

if len(st.session_state.chat_history) > 0:
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Starta en ny session"):
        st.session_state.chat_history = []
        if "senaste_referens" in st.session_state:
            del st.session_state.senaste_referens
        st.rerun()

# --- OSYNLIGT AUTO-SCROLL SKRIPT ---
if st.session_state.get("scroll_to_ny", False):
    components.html(
        """
        <script>
            // Vi använder en fördröjning för att överlista Streamlits inbyggda scroll-tvingande
            setTimeout(function() {
                const messages = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
                if (messages.length > 0) {
                    // Letar upp det allra sista meddelandet och lägger toppen av det i överkant
                    messages[messages.length - 1].scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            }, 500); // En halv sekunds väntan räcker
        </script>
        """,
        height=0
    )
    st.session_state.scroll_to_ny = False
