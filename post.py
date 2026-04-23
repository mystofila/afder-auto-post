import os
import random
import requests
import textwrap
import glob
import base64
from PIL import Image, ImageDraw, ImageFont
from google import genai
import cloudinary
import cloudinary.uploader
from nacl import encoding, public

# Config
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
FB_TOKEN = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"]
)

# Auto-renouvellement token
def save_token_to_github(new_token):
    gh_token = os.environ["GH_TOKEN"]
    repo = "mystofila/afder-auto-post"
    pub_r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={"Authorization": f"token {gh_token}"}
    )
    pub_data = pub_r.json()
    public_key_obj = public.PublicKey(pub_data["key"].encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(new_token.encode())
    encrypted_b64 = base64.b64encode(encrypted).decode()
    requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/FB_PAGE_TOKEN",
        headers={"Authorization": f"token {gh_token}"},
        json={"encrypted_value": encrypted_b64, "key_id": pub_data["key_id"]}
    )
    print("Token renouvelé et sauvegardé !")

r1 = requests.get(
    "https://graph.facebook.com/v19.0/oauth/access_token",
    params={
        "grant_type": "fb_exchange_token",
        "client_id": os.environ["FB_APP_ID"],
        "client_secret": os.environ["FB_APP_SECRET"],
        "fb_exchange_token": FB_TOKEN
    }
)
if "access_token" in r1.json():
    long_token = r1.json()["access_token"]
    save_token_to_github(long_token)
    FB_TOKEN = long_token
    print("Token longue durée activé !")
else:
    print(f"Renouvellement impossible : {r1.json()}")

# Générer le contenu
client = genai.Client(api_key=GEMINI_API_KEY)

themes = [
    "le courage de demander de l'aide face à la dépendance",
    "comment soutenir un proche en situation de dépendance",
    "l'importance de ne pas rester seul face à l'addiction",
    "les familles de personnes dépendantes ont besoin de soutien aussi",
    "reprendre confiance en soi après une dépendance",
    "l'entraide entre pairs dans le parcours de rétablissement",
    "comment parler de la dépendance sans jugement",
    "les rechutes font partie du chemin vers la guérison",
    "trouver de l'espoir quand tout semble perdu",
    "l'amour d'une famille peut aider à surmonter la dépendance",
    "accepter ses limites est un acte de courage",
    "le rétablissement est un chemin pas une destination",
    "briser le silence autour de la dépendance",
    "chaque jour sobre est une victoire",
    "la honte n'a pas sa place dans le parcours de guérison",
]
theme = random.choice(themes)

prompt = f"""Tu es un expert en accompagnement des personnes dépendantes et de leurs familles.
Génère un post Facebook bienveillant sur ce thème : {theme}

RÈGLES STRICTES :
- UNE phrase d'accroche courte et forte (max 12 mots)
- UNE phrase de corps courte (max 50 mots)
- 3 hashtags français à la fin
- TOTAL maximum 250 caractères hors hashtags
- UNE phrase de corps (max 12 mots, phrase COMPLETE avec point final)
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte, rien d'autre"""

response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents=prompt
)
caption = response.text.strip()
print(f"Caption générée : {caption}")

# Palettes
palettes = [
    {"bg1": (26, 42, 108),  "bg2": (45, 90, 160),   "accent": (100, 160, 220)},
    {"bg1": (60, 30, 100),  "bg2": (100, 60, 160),   "accent": (160, 120, 220)},
    {"bg1": (20, 80, 60),   "bg2": (40, 130, 100),   "accent": (80, 180, 140)},
    {"bg1": (100, 40, 20),  "bg2": (160, 80, 40),    "accent": (220, 140, 80)},
    {"bg1": (20, 60, 80),   "bg2": (40, 110, 140),   "accent": (80, 170, 200)},
    {"bg1": (80, 20, 60),   "bg2": (130, 50, 100),   "accent": (200, 100, 160)},
    {"bg1": (30, 70, 30),   "bg2": (60, 120, 60),    "accent": (100, 180, 100)},
    {"bg1": (60, 50, 20),   "bg2": (110, 90, 40),    "accent": (180, 150, 80)},
]
palette = random.choice(palettes)

# Logo
logos = glob.glob("*.png") + glob.glob("*.PNG")
logo_path = None
for logo in logos:
    if "logo" in logo.lower():
        logo_path = logo
        break
if not logo_path and logos:
    logo_path = logos[0]
print(f"Logo utilisé : {logo_path}")

def create_post_image(caption_text, filename):
    W, H = 1080, 1080
    MARGE = 80  # marge de sécurité sur les côtés
    ZONE = W - (MARGE * 2)  # zone de texte = 920px

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Dégradé vertical
    c1, c2 = palette["bg1"], palette["bg2"]
    for y in range(H):
        ratio = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Cercles décoratifs
    draw.ellipse([800, -150, 1250, 300], outline=palette["accent"], width=2)
    draw.ellipse([840, -110, 1210, 260], outline=palette["accent"], width=1)
    draw.ellipse([-150, 780, 300, 1230], outline=palette["accent"], width=2)

    # Ligne gauche
    draw.rectangle([0, 0, 8, H], fill=palette["accent"])

    try:
        font_accroche = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_corps = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 58)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except:
        font_accroche = ImageFont.load_default()
        font_corps = font_accroche
        font_brand = font_accroche

    # Logo
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = logo.resize((120, 120))
            img.paste(logo, (MARGE, 40), logo)
        except Exception as e:
            print(f"Erreur logo : {e}")

    # Séparer accroche et corps
    parties = caption_text.split(".")
    accroche = parties[0].strip()
    reste = ".".join(parties[1:]).strip() if len(parties) > 1 else ""
    corps = reste.split("#")[0].strip()
    hashtags_raw = "#" + reste.split("#", 1)[1] if "#" in reste else ""

    # Fonction pour wrapper le texte en respectant la zone
    def wrap_text(text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    # Accroche
    y_pos = 220
    lines_accroche = wrap_text(accroche, font_accroche, ZONE)
    for line in lines_accroche[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_accroche)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y_pos), line, font=font_accroche, fill="white")
        y_pos += 80

    # Séparateur
    draw.rectangle([(W - 120) / 2, y_pos + 10, (W + 120) / 2, y_pos + 18], fill=palette["accent"])
    y_pos += 55

    # Corps
    if corps:
        lines_corps = wrap_text(corps, font_corps, ZONE)
        for line in lines_corps[:6]:
            bbox = draw.textbbox((0, 0), line, font=font_corps)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2, y_pos), line, font=font_corps, fill=(210, 225, 255))
            y_pos += 60

    # Branding
    draw.rectangle([60, H - 100, W - 60, H - 94], fill=palette["accent"])
    brand = "@PairAidantPeerSupport"
    bbox = draw.textbbox((0, 0), brand, font=font_brand)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, H - 82), brand, font=font_brand, fill="white")

    img.save(filename, quality=95)
    print(f"Image créée : {filename}")

create_post_image(caption, "post.jpg")

# Uploader
result = cloudinary.uploader.upload("post.jpg")
image_url = result["secure_url"]
print(f"Image uploadée : {image_url}")

# Publier
publish_r = requests.post(
    f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
    data={
        "url": image_url,
        "caption": caption,
        "published": "true",
        "access_token": FB_TOKEN
    }
)
print(f"Status : {publish_r.status_code}")
print(f"Publication : {publish_r.json()}")
