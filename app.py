# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
import random
import re
from datetime import date
from openai import OpenAI

# Sätter en renare och mer minimalistisk sidlayout
st.set_page_config(layout="centered", page_title="novlx", page_icon="💋")

# --- INSTÄLLNINGAR ---
DEV_MODE = True
FILNAMN = "kategoriserade_berattelser.json"
ANVANDAR_FIL = "anvandare.json"

# --- INNEHÅLLSFILTER (SVARTLISTA) ---
FORBJUDNA_ORD = [
    "minderårig",
    "minderåriga",
    "barn",
    "olaglig",
    "incest",
    "våldtäkt",
    "våldtäkter",
    "pedofili",
    "djur",
    "grova personangrepp",
    "trakasserier",
    "hot"
]

def ar_innehall_tillatet(prompt_text):
    text_att_testa = prompt_text.lower()
    for ord in FORBJUDNA_ORD:
        if re.search(r'\b' + re.escape(ord) + r'\b', text_att_testa):
            return False
    return True

# --- 1. DATABAS FÖR ANVÄNDARE ---
def ladda_anvandare():
    if not os.path.exists(ANVANDAR_FIL):
        standard_data = {
            "admin": {"losenord": "novlx2026", "max_kvot": 100, "anvanda_idag": 0, "senaste_datum": str(date.today())},
            "gast": {"losenord": "test123", "max_kvot": 20, "anvanda_idag": 0, "senaste_datum": str(date.today())}
        }
        with open(ANVANDAR_FIL, "w", encoding="utf-8") as f:
            json.dump(standard_data, f, indent=4)
        return standard_data
    with open(ANVANDAR_FIL, "r", encoding="utf-8") as f:
        return json.load(f)

def spara_anvandare(data):
    with open(ANVANDAR_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

anvandar_db = ladda_anvandare()

if "inloggad_anvandare" not in st.session_state:
    st.session_state.inloggad_anvandare = None

# --- 2. GATEKEEPER: INLOGGNING OCH REGISTRERING ---
if st.session_state.inloggad_anvandare is None:
    st.title("🔒 Välkommen till novlx")
    st.write("Vänligen logga in eller skapa ett konto för att komma åt skrivarstudion.")
    
    tab1, tab2 = st.tabs(["Logga in", "Skapa konto"])
    
    with tab1:
        anvandarnamn = st.text_input("Användarnamn", key="login_user").strip().lower()
        losenord = st.text_input("Lösenord", type="password", key="login_pass")
        
        if st.button("Logga in"):
            if anvandarnamn in anvandar_db and anvandar_db[anvandarnamn]["losenord"] == losenord:
                st.session_state.inloggad_anvandare = anvandarnamn
                st.rerun()
            else:
                st.error("Fel användarnamn eller lösenord.")
                
    with tab2:
        ny_anvandare = st.text_input("Välj användarnamn", key="reg_user").strip().lower()
        nytt_losenord = st.text_input("Välj lösenord", type="password", key="reg_pass")
        over_18 = st.checkbox("Jag intygar att jag är minst 18 år gammal.")
        
        if st.button("Skapa konto"):
            if not ny_anvandare or not nytt_losenord:
                st.warning("Fyll i både användarnamn och lösenord.")
            elif ny_anvandare in anvandar_db:
                st.error("Användarnamnet är tyvärr redan upptaget.")
            elif not over_18:
                st.error("Åldersgräns: Du måste vara minst 18 år för att använda denna tjänst.")
            else:
                anvandar_db[ny_anvandare] = {
                    "losenord": nytt_losenord,
                    "max_kvot": 20,
                    "anvanda_idag": 0,
                    "senaste_datum": str(date.today())
                }
                spara_anvandare(anvandar_db)
                st.success("Konto skapat! Byt till fliken 'Logga in' för att starta.")
                
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

# --- SIDOMENY FÖR ANVÄNDAREN ---
with st.sidebar:
    st.subheader("👤 Ditt konto")
    st.write(f"Inloggad som: **{aktiv_anvandare.capitalize()}**")
    
    st.progress(min(anvanda_tokens / max_kvot, 1.0))
    st.write(f"🎟️ Använda generationer: {anvanda_tokens} av {max_kvot}")
    
    if st.button("Logga ut"):
        st.session_state.inloggad_anvandare = None
        st.session_state.chat_history = []
        st.rerun()
    st.markdown("---")

# --- SKOTTSÄKER KAMELEON-LÖSNING FÖR API-NYCKEL ---
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
        st.error("Systemfel: Hittar inte API-nyckeln. Kontrollera att filen eller secrets finns.")
        st.stop()

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

@st.cache_data
def ladda_bibliotek():
    if os.path.exists(FILNAMN):
        try:
            with open(FILNAMN, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

noveller = ladda_bibliotek()

# --- DESIGN: HUVUDAPPEN ---
st.title("✍️ novlx 💋")
st.markdown("<p style='font-style: italic; color: #888;'>Den interaktiva skrivarstudion för vuxenlitteratur.</p>", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if DEV_MODE and aktiv_anvandare == "admin":
    with st.sidebar:
        st.subheader("🛠️ Utvecklarverktyg")
        st.info(f"Databas laddad: {len(noveller)} noveller")
        if "debug_info" in st.session_state:
            st.markdown("### 🎯 Matchning:")
            st.write(f"**Titel:** {st.session_state.debug_info['titel']}")
            st.write(f"**Poäng:** {st.session_state.debug_info['poang']}")
        if "senaste_referens" in st.session_state:
            st.caption("Utdrag till AI:")
            st.code(st.session_state.senaste_referens[:150] + "...", language="text")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# DYNAMISKT TEXTFÄLT (FLIPP-FLOPP)
user_input = None

if len(st.session_state.chat_history) == 0:
    st.write("Beskriv en scen, en stämning eller en karaktär nedan för att påbörja berättelsen.")
    # FIX 1: Tog bort clear_on_submit=True så att texten sparas om man fastnar i filtret
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

def hitta_stil_referens(user_prompt):
    if not noveller:
        return "", None
    try:
        sokord = [ord.lower() for ord in user_prompt.split() if len(ord) > 3]
        traffar = []
        for n in noveller:
            analys = n.get("analys", {})
            titel = n.get("title", "")
            genre = analys.get("genre", "") or ""
            raw_tags = analys.get("tags")
            tags = raw_tags if isinstance(raw_tags, list) else []
            sammanfattning = analys.get("summary", "") or ""
            
            metadata = f"{titel} {genre} {' '.join(tags)} {sammanfattning}".lower()
            match_poang = sum(1 for ord in sokord if ord in metadata)
            if match_poang > 0:
                traffar.append((match_poang, n))
        
        if traffar:
            traffar.sort(key=lambda x: x[0], reverse=True)
            vinnare_poang, topp_val = random.choice(traffar[:3])
            text_snutt = topp_val.get("text", "")[:2000]
            referens = f"\n\n[SYSTEM-NOTERING: Inspireras av denna stil och ton:\n{text_snutt}...]"
            debug_info = {"titel": titel, "poang": vinnare_poang}
            return referens, debug_info
    except Exception:
        return "", None
    return "", None

if user_input:
    # 1. KONTROLLERA INNEHÅLLET
    if not ar_innehall_tillatet(user_input):
        st.error("🛑 Din text innehåller ord eller teman som bryter mot appens riktlinjer. Vänligen justera din beskrivning.")
    
    # 2. KONTROLLERA KVOTEN
    elif anvanda_tokens >= max_kvot:
        st.error("🛑 Du har nått din gräns för skapande idag. Kom tillbaka imorgon!")
    
    # 3. KÖR VIDARE
    else:
        kommando = user_input.strip().lower()
        ar_fortsattning = kommando in ["fortsätt", "mer", "vidare", ".", "..", "..."] and len(st.session_state.chat_history) > 0
        
        with st.chat_message("user"):
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
            "VIKTIGT: Avsluta ALLTID ditt svar med en fullständig mening och ett naturligt slut på stycket, oavsett hur lång texten blir."
        )
        
        if ar_fortsattning:
            system_prompt_content += "\n\n[VIKTIGT: Skriv nästa scen sömlöst där den förra slutade.]"
        else:
            system_prompt_content += f"{referens_text}"
            
        system_prompt = {"role": "system", "content": system_prompt_content}

        with st.chat_message("assistant"):
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
                    
                    # FIX 3: Tvinga omladdning när API-anropet är klart och sparat
                    st.rerun()
                    
                except Exception as e:
                    # Rensar bort användarens prompt från historiken om AI:n kraschade
                    st.session_state.chat_history.pop()
                    if DEV_MODE:
                        st.error(f"API-fel: {e}")
                    else:
                        st.error("Ett tillfälligt fel uppstod. Försök igen.")

if len(st.session_state.chat_history) > 0:
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Starta en ny session"):
        st.session_state.chat_history = []
        if "senaste_referens" in st.session_state:
            del st.session_state.senaste_referens
        st.rerun()