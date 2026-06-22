import json, re, shutil, os

ROOT = "/tmp/dental_chatbot_clinics"
TEMPLATE_DIR = f"{ROOT}/_template"  # a clean shared backend/skeleton to copy per clinic

with open(f"{ROOT}/_template_index.html") as f:
    HTML_TEMPLATE = f.read()

with open(f"{ROOT}/profiles.json") as f:
    profiles = json.load(f)

for slug, p in profiles.items():
    dest = f"{ROOT}/{slug}"
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(TEMPLATE_DIR, dest)
    # remove the Hiner sample clinic json + outreach assets from the template copy
    for stale in [f"{dest}/backend/clinics/hiner_family_dentistry.json",
                  f"{dest}/outreach-assets/hiner-chat-demo.gif",
                  f"{dest}/outreach-assets/hiner-chat-demo.png"]:
        if os.path.exists(stale):
            os.remove(stale)

    # ---- fill the HTML template ----
    html = HTML_TEMPLATE
    fills = {
        "TITLE": f"{p['practice_name']} — Virtual Assistant Preview",
        "PRACTICE_NAME": p["practice_name"],
        "ADDRESS": p["address"],
        "PHONE": p["phone"],
        "PHONE_TEL": p["phone_tel"],
        "HERO_TITLE": "Exceptional Care, <strong>Catered to You</strong>",
        "HERO_DESC": p["hero_desc"],
        "PILL_HOURS": p["pill_hours"],
        "PILL_INSURANCE": p["pill_insurance"],
        "PILL_SERVICES": p["pill_services"],
        "DOMAIN": p["domain"],
        "AVATAR_EMOJI": p["avatar_emoji"],
        "COLOR_ACCENT": p["color_accent"],
        "COLOR_ACCENT_DARK": p["color_accent_dark"],
        "COLOR_ACCENT_LIGHT": p["color_accent_light"],
        "COLOR_ACCENT_PALE": p["color_accent_pale"],
        "COLOR_DARK": p["color_dark"],
        "COLOR_DARK_LIGHT": p["color_dark_light"],
    }
    for key, val in fills.items():
        html = html.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if leftover:
        print(f"[{slug}] WARNING leftover placeholders: {set(leftover)}")
    with open(f"{dest}/frontend/index.html", "w") as f:
        f.write(html)

    # ---- config.js ----
    with open(f"{dest}/frontend/config.js", "w") as f:
        f.write(
            '// No secrets here -- this is a public, non-sensitive backend URL, safe to ship in a static file.\n'
            'window.API_BASE_URL = "https://dental-chatbot-demo.onrender.com";\n'
            f'window.CLINIC_SLUG = "{slug}";\n'
        )

    # ---- backend clinic data JSON ----
    clinic_json = {
        "slug": slug,
        "practice_name": p["practice_name"],
        "doctors": p["doctors"],
        "address": p["address"],
        "phone": p["phone"],
        "hours": p["hours_summary"],
        "booking_note": p["hours_summary"],
        "services": p["services"],
        "insurance_and_financing": p["insurance_and_financing"],
        "affiliations": [],
        "social": {},
        "system_prompt_extra": (
            f"If asked about emergencies, tell them to call {p['phone']} directly and still "
            "collect name and phone so the team can follow up. Be especially clear about hours "
            f"since this practice has limited availability: {p['hours_summary']}"
        ),
    }
    os.makedirs(f"{dest}/backend/clinics", exist_ok=True)
    with open(f"{dest}/backend/clinics/{slug}.json", "w") as f:
        json.dump(clinic_json, f, indent=2)

    print(f"Built: {slug}")

print("Done.")
