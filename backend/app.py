"""
Dental clinic demo chatbot backend -- NVIDIA NIM + Supabase edition.

LLM:      NVIDIA NIM (OpenAI-compatible endpoint), meta/llama-3.1-70b-instruct
Storage:  Supabase Postgres -- clinics table (config) + conversations table (captured leads/transcripts)
Fallback: if SUPABASE_URL/SUPABASE_KEY aren't set, falls back to local clinics/*.json files
          (so this still runs with zero external DB for quick local testing).

Run locally:
    pip install fastapi uvicorn openai supabase --break-system-packages
    export NVIDIA_API_KEY=nvapi-...
    export SUPABASE_URL=https://xxxx.supabase.co        # optional, falls back to JSON if unset
    export SUPABASE_KEY=eyJ...                          # service_role or anon key
    python app.py

Test:
    curl -X POST "http://localhost:8000/chat?clinic=hiner_family_dentistry" \
         -H "Content-Type: application/json" \
         -d '{"message": "Do you take walk-ins on Saturday?", "history": [], "session_id": "test-1"}'

Add a new clinic:
    With Supabase configured: INSERT a row into the clinics table (see supabase/schema.sql).
    Without Supabase (local/dev): drop a new <slug>.json file into clinics/.
"""

import json
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from supabase import create_client, Client as SupabaseClient
except ImportError:
    create_client = None
    SupabaseClient = None

CLINICS_DIR = Path(__file__).parent / "clinics"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
# Cheaper/faster fallback if you're burning through free credits during dev:
# MODEL = "meta/llama-3.1-8b-instruct"

# CORS: "*" is fine for local testing. Once deployed, replace with your actual
# Vercel domain (e.g. ["https://your-demo.vercel.app"]) -- see deployment guide.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")

app = FastAPI(title="Dental Demo Chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGINS] if ALLOWED_ORIGINS != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_supabase() -> Optional["SupabaseClient"]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not (url and key and create_client):
        return None
    return create_client(url, key)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    session_id: Optional[str] = None  # groups messages into one conversation/lead record


def load_clinic(slug: str) -> dict:
    """Supabase first, local JSON as fallback."""
    sb = get_supabase()
    if sb:
        res = sb.table("clinics").select("*").eq("slug", slug).limit(1).execute()
        if res.data:
            return res.data[0]
    path = CLINICS_DIR / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No clinic config found for '{slug}'")
    return json.loads(path.read_text())


def build_system_prompt(clinic: dict) -> str:
    def joined(key):
        val = clinic.get(key) or []
        return ", ".join(val) if isinstance(val, list) else str(val)

    return f"""You are the virtual front-desk assistant for {clinic['practice_name']}, a dental practice.
Speak warmly and concisely, like a helpful real receptionist -- not like a generic AI.

PRACTICE INFO (only use facts from here -- never invent details):
Doctors: {joined('doctors')}
Address: {clinic.get('address')}
Phone: {clinic.get('phone')}
Hours: {clinic.get('hours')}
Booking: {clinic.get('booking_note')}
Services: {joined('services')}
Insurance & financing: {joined('insurance_and_financing')}
Affiliations: {joined('affiliations')}

BEHAVIOR RULES:
{clinic.get('system_prompt_extra', '')}
- If asked something you don't have info on, say you'll have the team follow up -- never guess.
- Keep replies short (2-4 sentences) unless listing services.
- For any booking interest, collect name, phone number, and preferred day/time before ending the conversation.
"""


def log_conversation(clinic_slug: str, session_id: str, message: str, reply: str):
    """Best-effort lead/conversation capture. Never breaks the chat if logging fails."""
    sb = get_supabase()
    if not sb:
        return
    try:
        existing = sb.table("conversations").select("id, transcript").eq("session_id", session_id).limit(1).execute()
        new_turn = [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        if existing.data:
            transcript = existing.data[0]["transcript"] or []
            transcript.extend(new_turn)
            sb.table("conversations").update({"transcript": transcript}).eq("session_id", session_id).execute()
        else:
            sb.table("conversations").insert({
                "session_id": session_id,
                "clinic_slug": clinic_slug,
                "transcript": new_turn,
            }).execute()
    except Exception as e:
        print(f"[warn] conversation logging failed: {e}")


@app.get("/clinics")
def list_clinics():
    sb = get_supabase()
    if sb:
        res = sb.table("clinics").select("slug").execute()
        return {"clinics": [row["slug"] for row in res.data]}
    return {"clinics": [p.stem for p in CLINICS_DIR.glob("*.json")]}


@app.post("/chat")
def chat(req: ChatRequest, clinic: str = Query(..., description="clinic slug, e.g. hiner_family_dentistry")):
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="Run: pip install openai --break-system-packages")
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Set NVIDIA_API_KEY environment variable first")

    clinic_data = load_clinic(clinic)
    system_prompt = build_system_prompt(clinic_data)

    client = OpenAI(api_key=api_key, base_url=NVIDIA_BASE_URL)
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.message})

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=messages,
    )
    reply = response.choices[0].message.content

    session_id = req.session_id or str(uuid.uuid4())
    log_conversation(clinic, session_id, req.message, reply)

    return {"reply": reply, "session_id": session_id}


@app.get("/health")
def health():
    return {"status": "ok", "supabase_connected": get_supabase() is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
