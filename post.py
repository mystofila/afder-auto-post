import os
import json
import time
import random
import requests
import textwrap
import shutil
import glob
import base64
from PIL import Image, ImageDraw, ImageFont
from google import genai
import cloudinary
import cloudinary.uploader
from nacl import encoding, public

# Config
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
FB_USER_TOKEN = os.environ["FB_PAGE_TOKEN"]
FB_APP_ID = os.environ["FB_APP_ID"]
FB_APP_SECRET = os.environ["FB_APP_SECRET"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
GH_TOKEN = os.environ["GH_TOKEN"]

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"]
)

# Sauvegarder le token de page dans GitHub
repo = "mystofila/afder-auto-post"
pub_r = requests.get(
    f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
    headers={"Authorization": f"token {GH_TOKEN}"}
)
pub_data = pub_r.json()
pub_key = pub_data["key"]
key_id = pub_data["key_id"]

public_key_obj = public.PublicKey(pub_key.encode(), encoding.Base64Encoder())
sealed_box = public.SealedBox(public_key_obj)
encrypted = sealed_box.encrypt(FB_TOKEN.encode())
encrypted_b64 = base64.b64encode(encrypted).decode()

requests.put(
    f"https://api.github.com/repos/{repo}/actions/secrets/FB_PAGE_TOKEN",
    headers={"Authorization": f"token {GH_TOKEN}"},
    json={"encrypted_value": encrypted_b64, "key_id": key_id}
)
print("Token permanent sauvegardé dans GitHub !")

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
]
theme = random.choice(themes)

prompt = f"""Tu es un expert en accompagnement des personnes dépendantes et de leurs familles.
Génère un post Facebook bienveillant et inspirant sur ce thème : {theme}

IMPORTANT :
- Ton doux, empathique, sans jugement
- Message court et percutant
- Une phrase d'accroche forte
- Un message de soutien ou d'espoir
- 3 hashtags français pertinents
- Maximum 400 caractères au total
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte du post, rien d'autre"""

response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents=prompt
)
caption = response.text.strip()
print(f"Caption générée : {caption}")

# Télécharger l'image de fond
headers = {"User-Agent": "Mozilla/5.0"}
images_unsplash = [
    "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=1080",
    "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=1080",
    "https://images.unsplash.com/photo-1544027993-37dbfe43562a?w=1080",
    "https://images.unsplash.com/photo-1469571486292-0ba58a3f068b?w=1080",
    "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=1080",
    "https://images.unsplash.com/photo-1516302752625-fcc3c50ae61f?w=1080",
    "https://images.unsplash.com/photo-1542601906897-ecd9d9f4e01c?w=1080",
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=1080",
]
image_url_bg = random.choice(images_unsplash)
print(f"URL image fond : {image_url_bg}")

r = requests.get(image_url_bg, headers=headers)
with open("background.jpg", "wb") as f:
    f.write(r.content)
print("Image de fond téléchargée")

# Trouver le logo dans le repo
logos = glob.glob("*.png") + glob.glob("*.PNG")
print(f"Fichiers PNG trouvés : {logos}")
logo_path = None
for logo in logos:
    if "logo" in logo.lower():
        logo_path = logo
        break
if not logo_path and logos:
    logo_path = logos[0]
print(f"Logo utilisé : {logo_path}")

# Créer le visuel final
def create_post_image(caption_text, filename):
    W, H = 1080, 1080

    # Fond
    bg = Image.open("background.jpg").convert("RGB")
    bg = bg.resize((W, H))

    # Overlay sombre
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    bg_rgba = bg.convert("RGBA")
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)
    img = bg_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Logo en haut à gauche
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = logo.resize((150, 150))
            img.paste(logo, (40, 40), logo)
            print("Logo ajouté")
        except Exception as e:
            print(f"Erreur logo : {e}")

    # Bandeau coloré en bas
    colors = [
        (26, 42, 108),
        (45, 90, 160),
        (20, 80, 120),
        (60, 30, 100),
        (30, 100, 80),
    ]
    bandeau_color = random.choice(colors)
    bandeau_height = 200
    draw.rectangle([0, H - bandeau_height, W, H], fill=bandeau_color)

    # Polices
    try:
        font_bandeau = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_bandeau = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Texte dans le bandeau
    titre = caption_text.split(".")[0].strip()[:120]
    wrapped = textwrap.wrap(titre, width=40)
    y_pos = H - bandeau_height + 20
    for line in wrapped[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_bandeau)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y_pos), line, font=font_bandeau, fill="white")
        y_pos += 52

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
