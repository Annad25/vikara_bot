import streamlit as st
import json
from datetime import datetime
from groq import Groq
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = " " 

# --- GOOGLE CALENDAR SETUP ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'parnadebnath60669@gmail.com'

def create_calendar_event(summary, start_time_str, duration_mins=30):
    try:
        if "GOOGLE_JSON" in st.secrets:
             creds_dict = json.loads(st.secrets["GOOGLE_JSON"])
             creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
             creds = service_account.Credentials.from_service_account_file('google_key.json', scopes=SCOPES)

        service = build('calendar', 'v3', credentials=creds)

        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_dt = start_dt.replace(minute=start_dt.minute + duration_mins)

        description = (
        f"Booked by your Voice Agent.\n"
        f"Guest Name: {summary.replace('Meeting with ', '')}\n"
        f"Date Booked: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        }

        if guest_email:
        event['attendees'] = [{'email': guest_email}]

        # CALENDAR_ID
        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return True, event_result.get('htmlLink')
    except Exception as e:
        return False, str(e)

# --- AI AGENT (GROQ) ---
client = Groq(api_key=GROQ_API_KEY)

def transcribe_audio(audio_bytes):
    try:
        completion = client.audio.transcriptions.create(
            file=("input.wav", audio_bytes, "audio/wav"),
            model="whisper-large-v3",
            response_format="json",
            language="en"
        )
        return completion.text
    except Exception as e:
        st.error(f"Transcription Error: {e}")
        return None

def extract_slots(text, current_state):
    sys_prompt = f"""
    You are a scheduling assistant. 
    Current state: {current_state}
    
    INSTRUCTIONS:
    1. Extract fields: name, date (YYYY-MM-DD), time (HH:MM), title.
    2. If the user confirms, set "confirmed" to true.
    3. Today is {datetime.now().strftime('%Y-%m-%d')}.
    
    OUTPUT FORMAT:
    Return ONLY a raw JSON object. Do not add markdown formatting.
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"User said: '{text}'. Update the state JSON."}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0
        )
        content = completion.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        return {}

# --- STREAMLIT UI ---
st.title("🎙️ Voice Scheduling Agent")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your scheduling assistant. What is your name?"}]
if "slots" not in st.session_state:
    st.session_state.slots = {"name": None, "date": None, "time": None, "title": "Meeting", "confirmed": False}
if "last_processed" not in st.session_state:
    st.session_state.last_processed = None

# Display Chat History
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- AUDIO INPUT ---
audio_value = st.audio_input("Record your voice")
if audio_value and audio_value != st.session_state.last_processed:
    
    # Mark this audio as processed 
    st.session_state.last_processed = audio_value
    
    # 1. Transcribe
    text = transcribe_audio(audio_value)
    
    if text:
        st.session_state.messages.append({"role": "user", "content": text})
        
        # 2. Update Slots
        new_slots = extract_slots(text, st.session_state.slots)
        st.session_state.slots.update(new_slots)
        
        # 3. Determine Response
        response = ""
        slots = st.session_state.slots
        
        if slots["confirmed"]:
            success, link = create_calendar_event(
                f"{slots['title']} with {slots['name']}", 
                f"{slots['date']} {slots['time']}"
            )
            if success:
                response = f"Great! I've scheduled the meeting. View it here: {link}"
                # Resetting state fully for next user
                st.session_state.slots = {"name": None, "date": None, "time": None, "title": "Meeting", "confirmed": False}
            else:
                response = f"I tried to schedule it, but there was an error: {link}"
        
        elif not slots["name"]:
            response = "Got it. And what date would you like to meet?"
        elif not slots["date"]:
            response = f"Hi {slots['name']}, what date should I schedule?"
        elif not slots["time"]:
            response = "What time works best for you?"
        else:
            response = f"I have {slots['title']} with {slots['name']} on {slots['date']} at {slots['time']}. Shall I schedule this?"

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

