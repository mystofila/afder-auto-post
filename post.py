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
import urllib.request

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
- Maximum 200 caractères au total
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte du post, rien d'autre"""

response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents=prompt
)
caption = response.text.strip()
print(f"Caption générée : {caption}")

# Images Unsplash libres de droit selon le thème
images_unsplash = [
    "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=1080",  # main tendue
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=1080",  # soutien
    "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=1080",  # famille
    "https://images.unsplash.com/photo-1544027993-37dbfe43562a?w=1080",     # espoir
    "https://images.unsplash.com/photo-1516302752625-fcc3c50ae61f?w=1080",  # lumière
    "https://images.unsplash.com/photo-1469571486292-0ba58a3f068b?w=1080",  # entraide
    "https://images.unsplash.com/photo-1542601906897-ecd9d9f4e01c?w=1080",  # nature espoir
    "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=1080",  # chemin
]
image_url_bg = random.choice(images_unsplash)
print(f"URL image : {image_url_bg}")

# Télécharger l'image
urllib.request.urlretrieve(
    "https://raw.githubusercontent.com/mystofila/afder-auto-post/main/sans%20back.png",
    "logo.png"
)
print("Logo téléchargé")

# Créer le visuel final avec Pillow
def create_post_image(caption_text, filename):
    W, H = 1080, 1080

    # Charger et redimensionner l'image de fond
    bg = Image.open("background.jpg").convert("RGB")
    bg = bg.resize((W, H))

    # Overlay sombre pour lisibilité
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    bg_rgba = bg.convert("RGBA")
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)
    img = bg_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Charger le logo
    try:
        logo = Image.open("logo.png").convert("RGBA")
        logo_size = 150
        logo = logo.resize((logo_size, logo_size))
        img.paste(logo, (40, 40), logo)
        print("Logo ajouté")
    except Exception as e:
        print(f"Erreur logo : {e}")

    # Bandeau coloré en bas
    # Couleur selon le thème
    colors = [
        (26, 42, 108),   # Bleu foncé
        (45, 90, 160),   # Bleu moyen
        (20, 80, 120),   # Bleu canard
        (60, 30, 100),   # Violet foncé
        (30, 100, 80),   # Vert foncé
    ]
    bandeau_color = random.choice(colors)
    bandeau_height = 140
    draw.rectangle([0, H - bandeau_height, W, H], fill=bandeau_color)

    # Texte dans le bandeau
    try:
        font_bandeau = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_bandeau = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Titre dans le bandeau (première ligne du caption)
    titre = caption_text.split(".")[0].strip()[:50]
    wrapped = textwrap.wrap(titre, width=30)
    y_pos = H - bandeau_height + 20
    for line in wrapped[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_bandeau)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y_pos), line, font=font_bandeau, fill="white")
        y_pos += 52

    # Mention "image générée par IA" en bas à droite
    mention = "image generee par IA"
    bbox = draw.textbbox((0, 0), mention, font=font_small)
    w = bbox[2] - bbox[0]
    draw.text((W - w - 20, H - 35), mention, font=font_small, fill=(200, 200, 200))

    img.save(filename, quality=95)
    print(f"Image créée : {filename}")

create_post_image(caption, "post.jpg")

# Uploader sur Cloudinary
result = cloudinary.uploader.upload("post.jpg")
