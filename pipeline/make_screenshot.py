import json
from PIL import Image, ImageDraw, ImageFont

def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def wrap_text(text, fnt, max_width, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def build(slug, practice_name, avatar_emoji, accent_hex, dark_hex, question, answer, out_path):
    W, H = 420, 560
    accent = hex2rgb(accent_hex)
    dark = hex2rgb(dark_hex)
    white = (255, 255, 255)
    bg = (247, 249, 251)

    img = Image.new("RGB", (W, H), white)
    d = ImageDraw.Draw(img)

    # header
    d.rectangle([0, 0, W, 64], fill=dark)
    d.ellipse([14, 14, 50, 50], fill=(255, 255, 255, 40))
    f_emoji = font(20)
    d.text((22, 22), avatar_emoji, font=f_emoji)
    f_title = font(15, bold=True)
    f_sub = font(11)
    d.text((62, 16), practice_name, font=f_title, fill=white)
    d.text((62, 36), "Virtual Assistant", font=f_sub, fill=(255, 255, 255))

    # body bg
    d.rectangle([0, 64, W, H - 70], fill=bg)

    # bot greeting bubble
    f_msg = font(13)
    greeting = f"Hi! I'm the virtual assistant for {practice_name}. Ask me about hours, services, insurance, or to request an appointment."
    lines = wrap_text(greeting, f_msg, 260, d)
    bh = 20 + len(lines) * 18
    d.rounded_rectangle([46, 84, 46 + 280, 84 + bh], radius=12, fill=white, outline=(225, 230, 235))
    for i, line in enumerate(lines):
        d.text((60, 94 + i * 18), line, font=f_msg, fill=(40, 40, 40))
    d.ellipse([10, 84 + bh - 30, 38, 84 + bh - 2], fill=accent)
    d.text((17, 84 + bh - 26), avatar_emoji, font=font(13))

    y = 84 + bh + 16

    # user question bubble (right aligned)
    qlines = wrap_text(question, f_msg, 220, d)
    qh = 20 + len(qlines) * 18
    x1 = W - 16
    x0 = x1 - 240
    d.rounded_rectangle([x0, y, x1, y + qh], radius=12, fill=accent)
    for i, line in enumerate(qlines):
        tw = d.textlength(line, font=f_msg)
        d.text((x1 - 14 - tw, y + 10 + i * 18), line, font=f_msg, fill=white)
    y += qh + 16

    # bot answer bubble
    alines = wrap_text(answer, f_msg, 260, d)
    ah = 20 + len(alines) * 18
    d.rounded_rectangle([46, y, 46 + 290, y + ah], radius=12, fill=white, outline=(225, 230, 235))
    for i, line in enumerate(alines):
        d.text((60, y + 10 + i * 18), line, font=f_msg, fill=(40, 40, 40))
    d.ellipse([10, y + ah - 30, 38, y + ah - 2], fill=accent)
    d.text((17, y + ah - 26), avatar_emoji, font=font(13))

    # footer input row
    d.rectangle([0, H - 70, W, H], fill=white)
    d.line([0, H - 70, W, H - 70], fill=(225, 230, 235))
    d.rounded_rectangle([16, H - 50, W - 70, H - 16], radius=18, fill=bg, outline=(225, 230, 235))
    d.text((28, H - 42), "Type your message...", font=font(13), fill=(150, 155, 160))
    d.rounded_rectangle([W - 60, H - 50, W - 16, H - 16], radius=18, fill=accent)
    d.text((W - 46, H - 42), "Send", font=font(12, bold=True), fill=white)

    img.save(out_path)
    print(f"Saved {out_path}")

with open("/tmp/dental_chatbot_clinics/profiles.json") as f:
    profiles = json.load(f)

QA = {
    "the_dental_studio_miami": ("Do you have weekend hours?", "We're open Monday-Friday 8am-5pm, closed weekends. I can take your info now and the team will follow up to book you in first thing!"),
    "wow_dental_dallas": ("What are your Tuesday hours?", "Tuesdays we're open 1pm-5pm only. Want me to grab your name and number so we can lock in a time before it fills up?"),
    "bayfront_dental": ("Can I come in after work, like 5pm?", "Our hours are 8am-3pm Monday-Friday, so 5pm won't work for a walk-in -- but I can take your info now and have the team call you to find a time that fits."),
    "galaxia_dental_dallas": ("Are you open this Saturday?", "We're open every OTHER Saturday, 10am-3pm. Let me check what's next and grab your info so we can confirm your spot."),
    "north_miami_dental": ("Do you accept CareCredit?", "Yes! We accept CareCredit along with Evenly financing and all major credit cards. Want me to get your info started for a visit?"),
    "cool_creek_family_dental": ("I have a toothache, can I see someone today?", "I'm sorry you're dealing with that! Please call us directly at (512) 501-6022 for anything urgent -- and I'll also grab your name and number so the team can follow up right away."),
}

for slug, p in profiles.items():
    q, a = QA[slug]
    build(slug, p["practice_name"], p["avatar_emoji"], p["color_accent"], p["color_dark"], q, a,
          f"/tmp/dental_chatbot_clinics/{slug}/outreach-assets/chat-demo.png")
