import os
import json
import random
import base64
import glob
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
import cloudinary
import cloudinary.uploader
from nacl import encoding, public

# ─── Config ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
FB_TOKEN       = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID     = os.environ["FB_PAGE_ID"]
GH_TOKEN       = os.environ["GH_TOKEN"]
REPO           = "mystofila/afder-auto-post"

cloudinary.config(
    cloud_name  = os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key     = os.environ["CLOUDINARY_API_KEY"],
    api_secret  = os.environ["CLOUDINARY_API_SECRET"]
)

# ─── Token Facebook ───────────────────────────────────────────────────────────

def renouveler_token():
    """Échange le token courant contre un token longue durée et le sauvegarde."""
    r = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "grant_type":       "fb_exchange_token",
            "client_id":        os.environ["FB_APP_ID"],
            "client_secret":    os.environ["FB_APP_SECRET"],
            "fb_exchange_token": FB_TOKEN
        }
    )
    data = r.json()
    if "access_token" not in data:
        print(f"Renouvellement impossible : {data}")
        return FB_TOKEN

    nouveau_token = data["access_token"]
    _sauvegarder_secret_github("FB_PAGE_TOKEN", nouveau_token)
    print("Token longue durée activé et sauvegardé.")
    return nouveau_token


def _sauvegarder_secret_github(nom_secret, valeur):
    """Chiffre et sauvegarde une valeur dans les secrets GitHub Actions."""
    headers = {"Authorization": f"token {GH_TOKEN}"}

    pub_r    = requests.get(
        f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
        headers=headers
    )
    pub_data = pub_r.json()

    cle      = public.PublicKey(pub_data["key"].encode(), encoding.Base64Encoder())
    boite    = public.SealedBox(cle)
    chiffre  = base64.b64encode(boite.encrypt(valeur.encode())).decode()

    requests.put(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{nom_secret}",
        headers=headers,
        json={"encrypted_value": chiffre, "key_id": pub_data["key_id"]}
    )

# ─── Historique des thèmes ────────────────────────────────────────────────────

def charger_historique():
    """Récupère les thèmes déjà utilisés depuis state.json sur GitHub."""
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/contents/state.json",
        headers={"Authorization": f"token {GH_TOKEN}"}
    )
    if r.status_code == 200:
        contenu = base64.b64decode(r.json()["content"]).decode()
        data    = json.loads(contenu)
        return data.get("used", []), r.json()["sha"]
    return [], None


def sauvegarder_historique(theme_utilise, historique, sha):
    """Ajoute le thème utilisé dans state.json et le commit sur GitHub."""
    historique.append(theme_utilise)
    historique = historique[-10:]  # on garde les 10 derniers

    contenu = base64.b64encode(
        json.dumps({"used": historique}, ensure_ascii=False).encode()
    ).decode()

    payload = {"message": "chore: màj thèmes utilisés", "content": contenu}
    if sha:
        payload["sha"] = sha

    requests.put(
        f"https://api.github.com/repos/{REPO}/contents/state.json",
        headers={"Authorization": f"token {GH_TOKEN}"},
        json=payload
    )
    print(f"Historique mis à jour — thème sauvegardé : {theme_utilise}")

# ─── Thèmes ───────────────────────────────────────────────────────────────────

THEMES = [
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

# ─── Génération du contenu ────────────────────────────────────────────────────

def choisir_theme():
    """Choisit un thème non utilisé récemment."""
    historique, sha = charger_historique()
    disponibles     = [t for t in THEMES if t not in historique] or THEMES
    theme           = random.choice(disponibles)
    print(f"Thème choisi : {theme}")
    return theme, historique, sha


def generer_caption(theme):
    """Génère le texte du post via Gemini."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Tu es un expert en accompagnement des personnes dépendantes et de leurs familles.
Génère un post Facebook bienveillant sur ce thème : {theme}

RÈGLES STRICTES :
- UNE phrase d'accroche courte et forte (max 12 mots)
- UNE phrase de corps courte (max 12 mots, phrase COMPLÈTE avec point final)
- 3 hashtags français à la fin
- TOTAL maximum 250 caractères hors hashtags
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte, rien d'autre"""

    reponse = client.models.generate_content(model="gemma-4-26b-a4b-it", contents=prompt)
    caption = reponse.text.strip()
    print(f"Caption générée : {caption}")
    return caption

# ─── Création de l'image ──────────────────────────────────────────────────────

PALETTES = [
    {"bg1": (26, 42, 108),  "bg2": (45, 90, 160),   "accent": (100, 160, 220)},
    {"bg1": (60, 30, 100),  "bg2": (100, 60, 160),   "accent": (160, 120, 220)},
    {"bg1": (20, 80, 60),   "bg2": (40, 130, 100),   "accent": (80, 180, 140)},
    {"bg1": (100, 40, 20),  "bg2": (160, 80, 40),    "accent": (220, 140, 80)},
    {"bg1": (20, 60, 80),   "bg2": (40, 110, 140),   "accent": (80, 170, 200)},
    {"bg1": (80, 20, 60),   "bg2": (130, 50, 100),   "accent": (200, 100, 160)},
    {"bg1": (30, 70, 30),   "bg2": (60, 120, 60),    "accent": (100, 180, 100)},
    {"bg1": (60, 50, 20),   "bg2": (110, 90, 40),    "accent": (180, 150, 80)},
]

FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def trouver_logo():
    """Cherche un fichier logo PNG dans le répertoire courant."""
    for f in glob.glob("*.png") + glob.glob("*.PNG"):
        if "logo" in f.lower():
            return f
    fichiers = glob.glob("*.png") + glob.glob("*.PNG")
    return fichiers[0] if fichiers else None


def creer_image(caption, fichier_sortie):
    W, H   = 1080, 1080
    MARGE  = 80
    ZONE   = W - (MARGE * 2)
    palette = random.choice(PALETTES)
    logo    = trouver_logo()
    print(f"Logo utilisé : {logo}")

    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Dégradé vertical
    c1, c2 = palette["bg1"], palette["bg2"]
    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Éléments décoratifs
    draw.ellipse([800, -150, 1250, 300],  outline=palette["accent"], width=2)
    draw.ellipse([840, -110, 1210, 260],  outline=palette["accent"], width=1)
    draw.ellipse([-150, 780, 300, 1230],  outline=palette["accent"], width=2)
    draw.rectangle([0, 0, 8, H],          fill=palette["accent"])

    # Polices
    try:
        f_accroche = ImageFont.truetype(FONT_BOLD,    64)
        f_corps    = ImageFont.truetype(FONT_REGULAR, 58)
        f_brand    = ImageFont.truetype(FONT_BOLD,    34)
    except Exception:
        f_accroche = f_corps = f_brand = ImageFont.load_default()

    # Logo
    if logo:
        try:
            img_logo = Image.open(logo).convert("RGBA")
            img_logo = img_logo.resize((120, 120))
            img.paste(img_logo, (MARGE, 40), img_logo)
        except Exception as e:
            print(f"Erreur logo : {e}")

    # Découpage accroche / corps / hashtags
    parties  = caption.split(".")
    accroche = parties[0].strip()
    reste    = ".".join(parties[1:]).strip() if len(parties) > 1 else ""
    corps    = reste.split("#")[0].strip()

    def couper_texte(texte, police, largeur_max):
        mots, lignes, courante = texte.split(), [], ""
        for mot in mots:
            test = (courante + " " + mot).strip()
            if draw.textbbox((0, 0), test, font=police)[2] <= largeur_max:
                courante = test
            else:
                if courante:
                    lignes.append(courante)
                courante = mot
        if courante:
            lignes.append(courante)
        return lignes

    # Accroche (centré)
    y = 220
    for ligne in couper_texte(accroche, f_accroche, ZONE)[:3]:
        w = draw.textbbox((0, 0), ligne, font=f_accroche)[2]
        draw.text(((W - w) / 2, y), ligne, font=f_accroche, fill="white")
        y += 80

    # Séparateur
    draw.rectangle([(W - 120) / 2, y + 10, (W + 120) / 2, y + 18], fill=palette["accent"])
    y += 55

    # Corps (centré)
    if corps:
        for ligne in couper_texte(corps, f_corps, ZONE)[:6]:
            w = draw.textbbox((0, 0), ligne, font=f_corps)[2]
            draw.text(((W - w) / 2, y), ligne, font=f_corps, fill=(210, 225, 255))
            y += 60

    # Branding bas de page
    draw.rectangle([60, H - 100, W - 60, H - 94], fill=palette["accent"])
    brand = "@PairAidantPeerSupport"
    w     = draw.textbbox((0, 0), brand, font=f_brand)[2]
    draw.text(((W - w) / 2, H - 82), brand, font=f_brand, fill="white")

    img.save(fichier_sortie, quality=95)
    print(f"Image créée : {fichier_sortie}")

# ─── Publication Facebook ─────────────────────────────────────────────────────

def publier(image_locale, caption, token):
    """Upload l'image sur Cloudinary puis publie sur Facebook."""
    result    = cloudinary.uploader.upload(image_locale)
    image_url = result["secure_url"]
    print(f"Image uploadée : {image_url}")

    r = requests.post(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
        data={
            "url":          image_url,
            "caption":      caption,
            "published":    "true",
            "access_token": token
        }
    )
    print(f"Status : {r.status_code} — {r.json()}")

# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    token               = renouveler_token()
    theme, historique, sha = choisir_theme()
    caption             = generer_caption(theme)

    sauvegarder_historique(theme, historique, sha)

    creer_image(caption, "post.jpg")
    publier("post.jpg", caption, token)


if __name__ == "__main__":
    main()
