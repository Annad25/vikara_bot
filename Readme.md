# Meeting Scheduling Agent(voice+text) 🎙️

This project is a real time voice assistant that converses with users to gather meeting details and automatically books them into a Google Calendar.

### Deployed Agent
**[CLICK HERE TO TEST THE AGENT](https://vikarabot-gjplfwfomn2fi9dwwr4jq9.streamlit.app/)**

---

### How to Test
1. Click the deployed link above.
2. Click **"Speak to Agent"** and introduce yourself (e.g., *"Hi, I'm Name"*).
3. The agent will ask for a **date** and **time**. Respond naturally (e.g., *"I want to book a meeting for January 10th at 4 PM"*).
4. The agent will check for conflicts and ask for confirmation.
5. Say *"Yes"* or *"Book it"* to finalize.
6. Click the **"View Event"** link generated to see the real calendar entry.

---

### Calendar Integration
The calendar logic uses the **Google Calendar API (v3)** with a **Google Cloud Service Account** architecture for server-to-server authentication.

1. **Authentication:** The app uses a Google Service Account (`service_account.Credentials`). The JSON credentials are securely stored in Streamlit Secrets (`st.secrets`) for the deployed version, preventing sensitive key exposure in the repository.
2. **Conflict Detection:** Before booking, the agent queries the `events().list` endpoint. It defines a `timeMin` and `timeMax` based on the requested slot to check if any existing events overlap.
3. **Event Insertion:** If the slot is free, the agent constructs an event object with the user's name and summary and sends a POST request via `events().insert`.

---

### [Click Here to Watch the Demo Video](https://www.loom.com/share/f2623ed7fe964f3897070f66a999f54d)

---

### Local Setup 
*Note: To run this locally, you must provide your own API credentials. For security reasons, the repository does not include the private Service Account keys.*

1. **Clone the repository:**
   ```bash
   git clone <REPO_URL>
   cd <REPO_NAME>

2. **Install dependencies:**
     ```bash
     pip install -r requirements.txt

3. **Configure Secrets: Create a .streamlit/secrets.toml file in the root directory and add the following keys:**
    ```bash
    # 1. Your Groq API Key
    GROQ_API_KEY = " "
    
    # 2. Your Google Service Account JSON (as a string)
    # Make sure this service account has access to the target calendar.
    GOOGLE_JSON = """
    {
      "type": "service_account",
      "project_id": "...",
      "private_key_id": "...",
      ...
    
    }
    """
  ---
4. **Run the app**
   ```bash
   streamlit run app.py

