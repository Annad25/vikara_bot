import streamlit as st
import json
from datetime import datetime
from groq import Groq
from google.oauth2 import service_account
from googleapiclient.discovery import build
from gtts import gTTS
import io

# --- CONFIGURATION ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

CALENDAR_ID = 'parnadebnath60669@gmail.com' # Your Email
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- GOOGLE CALENDAR FUNCTION ---
def create_calendar_event(summary, start_time_str, duration_mins=30):
    try:
        if "GOOGLE_JSON" in st.secrets:
             creds_dict = json.loads(st.secrets["GOOGLE_JSON"])
             creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
             # Fallback for local testing if file exists
             creds = service_account.Credentials.from_service_account_file('google_key.json', scopes=SCOPES)

        service = build('calendar', 'v3', credentials=creds)

        # Parse the ISO format returned by LLM (YYYY-MM-DD HH:MM)
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_dt = start_dt.replace(minute=start_dt.minute + duration_mins)

        description = (
            f"Booked by AI Agent.\n"
            f"Meeting: {summary}\n"
            f"Booked on: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        }

        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return True, event_result.get('htmlLink')
    except Exception as e:
        return False, str(e)

# --- AI ENGINE ---
client = Groq(api_key=GROQ_API_KEY)

def text_to_speech_bytes(text):
    """Generates audio bytes from text using free gTTS"""
    try:
        tts = gTTS(text=text, lang='en')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

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

def process_conversation(user_input, current_state):
    """
    This is the Brain. It takes history + new input and returns:
    1. Updated State
    2. A Natural Language Response
    """
    
    current_date = datetime.now().strftime('%Y-%m-%d %A')
    
    sys_prompt = f"""
    You are a helpful Voice Scheduling Assistant.
    Today is {current_date}.
    
    YOUR GOAL: Gather specific details to book a calendar meeting.
    REQUIRED FIELDS: 'name' (user's name), 'date' (YYYY-MM-DD), 'time' (HH:MM 24hr format), 'title' (default "Meeting").
    
    CURRENT STATE (What we know so far):
    {json.dumps(current_state)}
    
    INSTRUCTIONS:
    1. Analyze the USER INPUT.
    2. MERGE new info with CURRENT STATE. 
       - If the user provides new info, update the field.
       - If the user does NOT mention a field, KEEP the value from CURRENT STATE. Do NOT set it to null.
    3. 'confirmed': Set to true ONLY if the user explicitly says "yes", "confirm", or "book it" AND all fields are present.
    4. 'reply_text': Generate a natural, conversational response to the user.
       - If fields are missing, ask for them politely (one or two at a time).
       - If all fields are present but not confirmed, repeat the details and ask to confirm.
       - If confirmed, say "Booking the meeting now."
    
    OUTPUT FORMAT:
    Return ONLY a raw JSON object. No markdown.
    Structure: {{ "name": "...", "date": "...", "time": "...", "title": "...", "confirmed": boolean, "reply_text": "..." }}
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"USER INPUT: '{user_input}'"}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0,
            response_format={"type": "json_object"} 
        )
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        st.error(f"LLM Error: {e}")
        # Return old state with error message
        current_state['reply_text'] = "Sorry, I had a brain freeze. Could you say that again?"
        return current_state

# --- STREAMLIT UI ---
st.set_page_config(page_title="AI Voice Scheduler", layout="centered")
st.title("🎙️ Smart Voice Scheduler")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your scheduling assistant. Who am I speaking with?"}]
if "slots" not in st.session_state:
    st.session_state.slots = {"name": None, "date": None, "time": None, "title": "Meeting", "confirmed": False}
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last_audio_id" not in st.session_state:
    st.session_state.last_audio_id = None

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
       
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3", autoplay=False)

# --- INPUT HANDLING ---
input_container = st.container()
processed_input = None

with input_container:
    # 1. Voice Input with DYNAMIC KEY
    
    audio_val = st.audio_input("Speak to Agent", key=f"audio_{st.session_state.audio_key}")
    
    # 2. Text Input
    text_val = st.chat_input("Or type here...")

    if audio_val:
        with st.spinner("Listening..."):
            processed_input = transcribe_audio(audio_val)
            st.session_state.audio_key += 1 
            
    elif text_val:
        processed_input = text_val

# --- LOGIC FLOW ---
if processed_input:
    # 1. Append User Message
    st.session_state.messages.append({"role": "user", "content": processed_input})
    
    # 2. Process with LLM (The Brain)
    with st.spinner("Thinking..."):
        # We pass the OLD slots so the LLM can remember history
        new_state = process_conversation(processed_input, st.session_state.slots)
        
        # Update session state with the new merged state
        st.session_state.slots.update(new_state)
        
        reply_text = new_state.get("reply_text", "I'm not sure what to say.")
        
        # 3. Check for Confirmation to Book
        if new_state.get("confirmed"):
            success, link = create_calendar_event(
                f"{new_state['title']} with {new_state['name']}", 
                f"{new_state['date']} {new_state['time']}"
            )
            if success:
                reply_text = "I've successfully booked your meeting. You can check your calendar."
                # Append link 
                final_display_text = reply_text + f"\n\n[View Event]({link})"
                
                # Reset state after booking
                st.session_state.slots = {"name": None, "date": None, "time": None, "title": "Meeting", "confirmed": False}
            else:
                reply_text = f"I tried to book it, but Google Calendar gave me an error: {link}"
                final_display_text = reply_text
        else:
            final_display_text = reply_text

    # 4. Generate Voice Reply
    audio_reply = text_to_speech_bytes(reply_text)

    # 5. Append Assistant Message
    st.session_state.messages.append({
        "role": "assistant", 
        "content": final_display_text, 
        "audio": audio_reply
    })

    # 6.  update UI
    st.rerun()

# Debugging: Show State
with st.expander("Debug: Internal State"):
    st.json(st.session_state.slots)
