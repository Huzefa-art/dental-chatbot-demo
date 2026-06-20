# Deployment guide — NVIDIA NIM + Render + Vercel + Supabase

Verified locally before writing this: `/health`, `/clinics`, clinic loading (JSON fallback), system
prompt build, and the chat endpoint's error handling all pass. The only thing untested end-to-end is
a live NVIDIA key and a live Supabase project, since those need your own credentials.

## Step-by-step sequence

**1. Get an NVIDIA API key**
Sign up free at build.nvidia.com (no credit card). Grab your `nvapi-...` key. You get 1,000 free
credits (extendable to 5,000) and a 40 requests/minute cap — plenty for demos and early outreach.

**2. Create the Supabase project**
- New project at supabase.com (free tier: 2 projects max, 500MB DB).
- Open the SQL Editor, paste in `supabase/schema.sql`, run it. This creates `clinics` and
  `conversations` tables and seeds Hiner Family Dentistry.
- Grab your Project URL and the `service_role` key (Settings > API) — keep the service_role key
  server-side only (Render env var), never in the frontend.

**3. Push this folder to a GitHub repo**
Render and Vercel both deploy from git. `git init`, commit `backend/`, `frontend/`, `supabase/`,
push to a new GitHub repo.

**4. Deploy the backend to Render**
- New > Web Service > connect the repo > set Root Directory to `backend`.
- Render will read `render.yaml` (build command, start command already set).
- In the dashboard, set the env vars `NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (these are
  marked `sync: false` in render.yaml specifically so they're never committed to git).
- Deploy. Copy the resulting URL, e.g. `https://dental-demo-chatbot.onrender.com`.

**5. Deploy the frontend to Vercel**
- New Project > import the same repo > set Root Directory to `frontend`.
- No build step needed (`vercel.json` already disables it) — it's plain HTML/JS.
- Before or after deploying, edit `frontend/config.js`: set `window.API_BASE_URL` to your real
  Render URL from step 4. Commit and push (Vercel auto-redeploys), or just edit it in the Vercel
  dashboard's file editor for a one-off change.
- Deploy. You now have a real shareable link, e.g. `https://your-demo.vercel.app`.

**6. Lock down CORS**
Go back to Render, set `ALLOWED_ORIGINS` to your actual Vercel URL (not `*`), redeploy. This stops
random sites from calling your backend directly.

**7. Test the live link**
Open the Vercel URL on a phone or a different machine, send a message, confirm a reply comes back.
First request after idle time will be slow (see cold starts below) — that's expected, not broken.

## Free-tier gotchas

- **Render free tier sleeps after 15 minutes idle**, 30-60 second cold start on the next request.
  The widget now shows a "connecting..." message during this so it doesn't look broken to a
  prospect. If you're about to send a demo link for an actual sales call, hit the URL yourself
  60 seconds beforehand to wake it up.
- **Supabase free projects pause after 7 days with zero requests.** If a clinic's demo link sits
  unused for a week, the database goes to sleep until you manually unpause it in the dashboard.
  A free cron ping (GitHub Actions, once a day) avoids this if it becomes annoying.
- **Vercel Hobby tier is licensed for personal/non-commercial use.** Fine for building and even
  early outreach, but once this is generating real client revenue, the honest move is Pro ($20/mo).
- **NVIDIA's free tier is credit-based, not a recurring allowance** — 1,000-5,000 credits total,
  then it's gone. Fine for dozens of demo conversations; will not survive real production volume
  across multiple paying clients without moving to a paid key.

## What breaks first under real traffic, and the order you'll likely upgrade

1. **NVIDIA credits run out first** if multiple clinics are live and getting real patient traffic —
   move to a paid NVIDIA key (pay-per-token, comparable to other LLM providers) or swap the
   `base_url`/`model` back to a different provider; the code is a two-line change either way.
2. **Render cold starts become a real problem** once you have paying clients, not just demos — a
   patient hitting a sleeping bot at 11pm and waiting a minute is a bad first impression. This is
   the most likely first paid upgrade: Render Starter is ~$7/month and removes sleep entirely.
3. **Supabase 500MB** will hold thousands of conversations comfortably — this is the least likely
   thing to break early. The 2-project cap matters more if you ever want a separate staging
   environment; the free tier handles many clinics fine since they're just rows, not projects.
4. **Vercel limits (100GB bandwidth, 100K function calls)** won't be the bottleneck for a static
   widget — you'll move off Hobby for the licensing reason above before you hit a real usage limit.

Net: this stack runs at $0/month through building, testing, and early outreach. The first real
dollar you'll likely spend is ~$7/month on Render once you have a paying client who expects the
bot to respond instantly, not after a coffee-break-length cold start.
