# Clinic generator pipeline

Fast path for onboarding a new clinic lead without hand-editing HTML per clinic.

1. Add an entry to `profiles.json` with the clinic's real researched data
   (name, address, phone, hours, colors, services, insurance, etc).
2. Run `python3 generate.py` -- fills `clinic_template.html` for every profile
   and outputs a ready folder per clinic under `../<slug>/` with:
     - frontend/index.html + config.js
     - backend/clinics/<slug>.json
3. Run `python3 make_screenshot.py` -- auto-generates a branded static
   screenshot (no browser, no animation) per clinic for the outreach email.
4. Copy the generated frontend/index.html into `frontend/clinics/<slug>/`,
   the backend JSON into `backend/clinics/<slug>.json`, and the screenshot
   into `outreach-assets/<slug>-chat-demo.png` in the main repo, then
   git push -- Render/Vercel auto-deploy picks it up from there.
