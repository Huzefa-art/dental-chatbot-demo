# Dental Demo Chatbot — NVIDIA NIM + Render + Vercel + Supabase, no Voiceflow, no dashboards

Tested and verified locally: backend loads, `/health`, `/clinics`, clinic config loading (with
Supabase-first / JSON-fallback), system prompt building, and `/chat` error handling all pass.
Live LLM calls and live Supabase need your own NVIDIA + Supabase credentials to test end-to-end —
see `DEPLOYMENT.md` for the exact steps.

## Structure
```
backend/    FastAPI app -- NVIDIA NIM for the LLM, Supabase for clinic configs + captured leads
  app.py
  requirements.txt
  render.yaml
  clinics/*.json        (fallback if Supabase isn't configured yet)
frontend/   Static chat widget -- deploys to Vercel as-is, zero build step
  index.html
  config.js             (the one line you edit per-deploy: your Render backend URL)
  vercel.json
supabase/
  schema.sql            run once in the Supabase SQL editor -- creates tables + seeds Hiner Family Dentistry
DEPLOYMENT.md            full step-by-step + free-tier limits + what breaks first
```

## Run it locally
```
cd backend
pip install -r requirements.txt --break-system-packages
export NVIDIA_API_KEY=nvapi-your-key-here
python app.py
```
Open `frontend/index.html` in a browser — it talks to `http://localhost:8000` by default
(`frontend/config.js`). Supabase is optional locally; without it, the backend reads
`backend/clinics/*.json` directly.

## Add the next clinic — zero manual UI work
With Supabase live: INSERT a row into the `clinics` table (same fields as the seed row in
`supabase/schema.sql`). Without Supabase: drop a new `<slug>.json` into `backend/clinics/`.
Either way, no new project, no dashboard, no upload screen. I can generate the next clinic's
config directly from their real site the same way I built Hiner's — just say which of the
remaining 7 verified clinics to do next (Dental Defenders, North Miami Dental, The Dental
Studio Miami, WOW Dental, Galaxia Dental, Cool Creek Family Dental, Bayfront Dental).

## Going live
See `DEPLOYMENT.md` — full sequence from NVIDIA signup to a real clickable link, plus exactly
what free-tier limits to expect and what you'll pay for first once there's real traffic.

## Why this instead of Voiceflow
Voiceflow's API manages documents inside a project you still create by hand in their dashboard;
per-client setup still happens through their UI either way. This version is plain code on a stack
that matches your own resume (FastAPI, RAG-style system prompting, Postgres) — new clinic is a row
or a file, not a dashboard click, and you can extend it y