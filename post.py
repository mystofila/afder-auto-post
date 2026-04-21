import os
import json
import time
import random
import requests
import textwrap
from PIL import Image, ImageDraw, ImageFont
from google import genai
import cloudinary
import cloudinary.uploader
import glob

# Config
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
FB_TOKEN = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"]
)

# Générer le contenu avec Gemini
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
Génère un post Facebook bienveillant et inspirant sur ce thème : {theme}

IMPORTANT :
- Ton doux, empathique, sans jugement
- Une phrase d'accroche forte en premier, MAXIMUM 50 caractères, qui soit une phrase COMPLÈTE
- Un message de soutien ou d'espoir
- 3 hashtags français pertinents à la fin
- Maximum 400 caractères au total
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte du post, rien d'autre"""

response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents=prompt
)
caption = response.text.strip()
print(f"Caption générée : {caption}")

# Palettes de couleurs bienveillantes
palettes = [
    {"bg1": (26, 42, 108),  "bg2": (45, 90, 160),   "accent": (100, 160, 220)},  # Bleu profond
    {"bg1": (60, 30, 100),  "bg2": (100, 60, 160),   "accent": (160, 120, 220)},  # Violet doux
    {"bg1": (20, 80, 60),   "bg2": (40, 130, 100),   "accent": (80, 180, 140)},   # Vert espoir
    {"bg1": (100, 40, 20),  "bg2": (160, 80, 40),    "accent": (220, 140, 80)},   # Terre chaud
    {"bg1": (20, 60, 80),   "bg2": (40, 110, 140),   "accent": (80, 170, 200)},   # Bleu canard
    {"bg1": (80, 20, 60),   "bg2": (130, 50, 100),   "accent": (200, 100, 160)},  # Rose profond
    {"bg1": (30, 70, 30),   "bg2": (60, 120, 60),    "accent": (100, 180, 100)},  # Vert nature
    {"bg1": (60, 50, 20),   "bg2": (110, 90, 40),    "accent": (180, 150, 80)},   # Or doux
]
palette = random.choice(palettes)

# Trouver le logo
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
    draw.ellipse([-110, 820, 260, 1190], outline=palette["accent"], width=1)

    # Ligne décorative gauche
    draw.rectangle([0, 0, 8, H], fill=palette["accent"])

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 58)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except:
        font_title = ImageFont.load_default()
        font_body = font_title
        font_small = font_title
        font_brand = font_title

    # Logo en haut à gauche
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = logo.resize((130, 130))
            img.paste(logo, (40, 40), logo)
        except Exception as e:
            print(f"Erreur logo : {e}")

    # Séparer accroche et corps du texte
    phrases = caption_text.split(".")
    accroche = phrases[0].strip() if phrases else caption_text
    reste = ".".join(phrases[1:]).strip() if len(phrases) > 1 else ""

    # Accroche en grand
    wrapped_accroche = textwrap.wrap(accroche, width=28)
    y_pos = 220
    for line in wrapped_accroche[:4]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y_pos), line, font=font_title, fill="white")
        y_pos += 72

    # Ligne de séparation
    draw.rectangle([(W - 120) / 2, y_pos + 15, (W + 120) / 2, y_pos + 22], fill=palette["accent"])
    y_pos += 55

    # Corps du texte (sans hashtags)
    corps = reste.split("#")[0].strip() if "#" in reste else reste
    if corps:
        wrapped_corps = textwrap.wrap(corps, width=40)
        for line in wrapped_corps[:6]:
            bbox = draw.textbbox((0, 0), line, font=font_body)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2, y_pos), line, font=font_body, fill=(210, 225, 255))
            y_pos += 44

    # Ligne et branding en bas
    draw.rectangle([60, H - 100, W - 60, H - 94], fill=palette["accent"])
    brand = "@PairAidantPeerSupport"
    bbox = draw.textbbox((0, 0), brand, font=font_brand)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, H - 82), brand, font=font_brand, fill="white")

    img.save(filename, quality=95)
    print(f"Image créée : {filename}")

create_post_image(caption, "post.jpg")

# Uploader sur Cloudinary
result = cloudinary.uploader.upload("post.jpg")
image_url = result["secure_url"]
print(f"Image uploadée : {image_url}")

# Publier sur Facebook
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
