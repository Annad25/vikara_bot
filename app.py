import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import json
import os
from datetime import datetime
from groq import Groq
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---

if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    # FALLBACK
    GROQ_API_KEY = "" 

# --- GOOGLE CALENDAR SETUP ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'google_key.json'

def create_calendar_event(summary, start_time_str, duration_mins=30):
    """
    Creates an event in the primary calendar shared with the service account.
    start_time_str format: 'YYYY-MM-DD HH:MM'
    """
    try:
        # Load credentials from secrets
        if "GOOGLE_JSON" in st.secrets:
             creds_dict = json.loads(st.secrets["GOOGLE_JSON"])
             creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
             creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

        service = build('calendar', 'v3', credentials=creds)

        # Parse time
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_dt = start_dt.replace(minute=start_dt.minute + duration_mins) 

        event = {
            'summary': summary,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
        }

        event_result = service.events().insert(calendarId='primary', body=event).execute()
        return True, event_result.get('htmlLink')
    except Exception as e:
        return False, str(e)

# --- AI AGENT (GROQ) ---
client = Groq(api_key=GROQ_API_KEY)

def transcribe_audio(audio_bytes):
    """Uses Groq Whisper (free & fast)"""
    try:
        completion = client.audio.transcriptions.create(
            file=("input.wav", audio_bytes, "audio/wav"),
            model="whisper-large-v3",
            response_format="json",
            language="en"
        )
        return completion.text
    except Exception as e:
        return None

def extract_slots(text, current_state):
    # 1. prompt
    sys_prompt = f"""
    You are a scheduling assistant. 
    Current state: {current_state}
    
    INSTRUCTIONS:
    1. Extract fields: name, date (YYYY-MM-DD), time (HH:MM), title.
    2. If the user confirms, set "confirmed" to true.
    3. Today is {datetime.now().strftime('%Y-%m-%d')}.
    
    OUTPUT FORMAT:
    You must return ONLY a raw JSON object. Do not add markdown formatting like ```json.
    Do not add any conversational text. Just the JSON.
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
        
        # 3. Manual Cleanup 
        content = completion.choices[0].message.content
        
        # strip ```json 
        content = content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(content)
        
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        # Return empty dict
        return {}

# --- STREAMLIT UI ---
st.title("🎙️ Voice Scheduling Agent")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your scheduling assistant. What is your name?"}]
if "slots" not in st.session_state:
    st.session_state.slots = {"name": None, "date": None, "time": None, "title": "Meeting", "confirmed": False}

# Display Chat History
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Audio Input
# We use a key to force a refresh on new recording
#audio_ctx = webrtc_streamer(
    #key="speech-input",
    #mode=WebRtcMode.SENDONLY,
    #rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    #media_stream_constraints={"video": False, "audio": True},
#)

# Processing Logic
#if audio_ctx.state.playing and audio_ctx.audio_receiver:
    # Logic to grab audio frames
    #st.info("Real-time streaming is active.")

# --- ALTERNATIVE: SIMPLE AUDIO INPUT (Reliable Fallback) ---
audio_value = st.audio_input("Record your voice")

if audio_value:
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
            # Create Event
            success, link = create_calendar_event(
                f"{slots['title']} with {slots['name']}", 
                f"{slots['date']} {slots['time']}"
            )
            if success:
                response = f"Great! I've scheduled the meeting. View it here: {link}"
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

# Debug View
st.sidebar.write("Internal State:", st.session_state.slots)
