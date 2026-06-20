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

LEAD QUALIFICATION (do this naturally, inside the conversation -- never show a form or a list of questions):
- Within the first couple of exchanges, try to infer whether they're a new or existing patient, and
  why they're reaching out (routine cleaning, pain/emergency, cosmetic interest, pricing/insurance
  question, or just browsing). Infer this from what they say rather than interrogating them -- only
  ask directly if it's genuinely unclear after a turn or two.
- Near the end of the conversation (once their main question is answered, or a booking/callback is
  set up), casually ask how they heard about the practice (search engine, a friend's referral, social
  media, or an ad). Keep it light, e.g. "One quick thing before you go -- how'd you find us?"
- If you can't resolve something yourself (a complex insurance question, or they explicitly want to
  talk to a human), offer to take their name and phone number for a callback -- this is separate from
  a booking request; don't conflate the two.
"""


EXTRACTION_SYSTEM_PROMPT = """You extract structured lead data from a dental clinic chatbot conversation.
Read the transcript and return ONLY a JSON object (no prose, no markdown fences) with these keys:

- patient_type: one of "new", "existing", or null if unresolved
- reason_for_visit: one of "routine_cleaning", "pain_emergency", "cosmetic", "pricing", "browsing", or null
- referral_source: one of "search", "referral", "social_media", "ad", "other", or null
- request_type: one of "booking", "callback_request", "general_inquiry", or null
- lead_name: the patient's name if they gave one, else null
- lead_phone: the patient's phone number if they gave one, else null
- preferred_time: their preferred appointment day/time if mentioned, else null

Use null for anything not clearly stated or implied in the transcript -- never guess or invent values.
"""


def extract_lead_fields(client: "OpenAI", transcript: list) -> dict:
    """Best-effort structured extraction from the running transcript. Never breaks the chat."""
    empty = {
        "patient_type": None, "reason_for_visit": None, "referral_source": None,
        "request_type": None, "lead_name": None, "lead_phone": None, "preferred_time": None,
    }
    try:
        convo_text = "\n".join(f"{t['role']}: {t['content']}" for t in transcript)
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            temperature=0,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": convo_text},
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        empty.update({k: parsed.get(k) for k in empty if parsed.get(k)})
        return empty
    except Exception as e:
        print(f"[warn] lead field extraction failed: {e}")
        return empty


FIELD_COLUMNS = ["patient_type", "reason_for_visit", "referral_source", "request_type",
                  "lead_name", "lead_phone", "preferred_time"]


def log_conversation(client: "OpenAI", clinic_slug: str, session_id: str, message: str, reply: str):
    """Best-effort lead/conversation capture + structured field extraction. Never breaks the chat if it fails."""
    sb = get_supabase()
    if not sb:
        return
    try:
        select_cols = "id, transcript, " + ", ".join(FIELD_COLUMNS)
        existing = sb.table("conversations").select(select_cols) \
            .eq("session_id", session_id).limit(1).execute()
        new_turn = [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        prior_row = existing.data[0] if existing.data else {}
        transcript = (prior_row.get("transcript") or []) + new_turn

        extracted = extract_lead_fields(client, transcript)
        # Never let a later "unresolved" extraction erase a field we already captured.
        fields = {k: (extracted.get(k) or prior_row.get(k)) for k in FIELD_COLUMNS}

        if existing.data:
            sb.table("conversations").update({"transcript": transcript, **fields}).eq("session_id", session_id).execute()
        else:
            sb.table("conversations").insert({
                "session_id": session_id,
                "clinic_slug": clinic_slug,
                "transcript": new_turn,
                **fields,
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
    log_conversation(client, clinic, session_id, req.message, reply)

    return {"reply": reply, "session_id": session_id}


@app.get("/health")
def health():
    return {"status": "ok", "supabase_connected": get_supabase() is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
