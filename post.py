import os
import random
import base64
import glob
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
import cloudinary
import cloudinary.uploader
from nacl import encoding, public

# ─── Config ───────────────────────────────────────────────────────────────────

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
FB_TOKEN         = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID       = os.environ["FB_PAGE_ID"]
GH_TOKEN         = os.environ["GH_TOKEN"]
REPO             = "mystofila/afder-auto-post"
JFT_URL          = "https://www.jftna.org/jft/"

cloudinary.config(
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key    = os.environ["CLOUDINARY_API_KEY"],
    api_secret = os.environ["CLOUDINARY_API_SECRET"]
)

# ─── Token Facebook ───────────────────────────────────────────────────────────

def renouveler_token():
    r = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         os.environ["FB_APP_ID"],
            "client_secret":     os.environ["FB_APP_SECRET"],
            "fb_exchange_token": FB_TOKEN
        }
    )
    data = r.json()
    if "access_token" not in data:
        print(f"Renouvellement impossible : {data}")
        return FB_TOKEN
    nouveau_token = data["access_token"]
    _sauvegarder_secret_github("FB_PAGE_TOKEN", nouveau_token)
    print("Token longue duree active et sauvegarde.")
    return nouveau_token


def _sauvegarder_secret_github(nom_secret, valeur):
    headers  = {"Authorization": f"token {GH_TOKEN}"}
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

# ─── Scraping JFT ─────────────────────────────────────────────────────────────

def scraper_jft():
    r = requests.get(JFT_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    # Debug : afficher les 3000 premiers caracteres du HTML brut
    print("=== HTML BRUT (3000 chars) ===")
    print(r.text[:3000])
    print("=== FIN HTML ===")

    soup = BeautifulSoup(r.text, "html.parser")

    # Essayer td, puis p, puis div
    blocs = soup.find_all("td") or soup.find_all("p") or soup.find_all("div")
    cellules = [b.get_text(separator=" ", strip=True) for b in blocs]
    cellules = [c for c in cellules if len(c) > 3]

    print(f"Blocs extraits ({len(cellules)}) :")
    for i, c in enumerate(cellules):
        print(f"  [{i}] {c[:100]}")

    if not cellules:
        raise ValueError("Aucun contenu extrait — voir HTML brut ci-dessus")

    titre     = cellules[1] if len(cellules) > 1 else cellules[0]
    jft_ligne = next((c for c in reversed(cellules) if c.lower().startswith("just for today")), cellules[-1])

    print(f"\nJFT extrait — Titre : {titre}")
    print(f"Pensee du jour : {jft_ligne}")
    return {"titre": titre, "jft": jft_ligne}

# ─── Génération du post ───────────────────────────────────────────────────────

def generer_caption(jft_data):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    prompt = (
        "Tu es un redacteur bienveillant pour AFDER "
        "(Association Francaise des Dependants en Retablissement).\n"
        "Voici la pensee du jour en anglais :\n\n"
        f"TITRE : {jft_data['titre']}\n"
        f"PENSEE DU JOUR : {jft_data['jft']}\n\n"
        "Ta mission : traduire et adapter cette pensee en francais.\n\n"
        "REGLES OBLIGATOIRES :\n"
        "1. Commence TOUJOURS par \"Juste pour aujourd'hui :\"\n"
        "2. Maximum 15 mots apres les deux points\n"
        "3. Phrase COMPLETE avec point final\n"
        "4. Remplace NA / Narcotics Anonymous par AFDER\n"
        "5. Remplace Dieu / Higher Power / God / spiritual par "
        "la force du collectif, l entraide ou la communaute\n"
        "6. Reponds UNIQUEMENT avec la phrase, rien d autre"
    )

    reponse = client.chat.completions.create(
        model    = "deepseek-chat",
        messages = [{"role": "user", "content": prompt}]
    )
    caption = reponse.choices[0].message.content.strip()

    if not caption.lower().startswith("juste pour aujourd"):
        caption = "Juste pour aujourd'hui : " + caption

    print(f"\nCaption generee :\n{caption}")
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
    for f in glob.glob("*.png") + glob.glob("*.PNG"):
        if "logo" in f.lower():
            return f
    fichiers = glob.glob("*.png") + glob.glob("*.PNG")
    return fichiers[0] if fichiers else None


def creer_image(caption, fichier_sortie):
    W, H    = 1080, 1080
    MARGE   = 80
    ZONE    = W - (MARGE * 2)
    palette = random.choice(PALETTES)
    logo    = trouver_logo()

    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Degradé vertical
    c1, c2 = palette["bg1"], palette["bg2"]
    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Elements decoratifs
    draw.ellipse([800, -150, 1250, 300],  outline=palette["accent"], width=2)
    draw.ellipse([840, -110, 1210, 260],  outline=palette["accent"], width=1)
    draw.ellipse([-150, 780, 300, 1230],  outline=palette["accent"], width=2)
    draw.rectangle([0, 0, 8, H],          fill=palette["accent"])

    # Polices
    try:
        f_texte = ImageFont.truetype(FONT_BOLD, 72)
        f_brand = ImageFont.truetype(FONT_BOLD, 34)
    except Exception:
        f_texte = f_brand = ImageFont.load_default()

    # Logo
    if logo:
        try:
            img_logo = Image.open(logo).convert("RGBA")
            img_logo = img_logo.resize((120, 120))
            img.paste(img_logo, (MARGE, 40), img_logo)
        except Exception as e:
            print(f"Erreur logo : {e}")

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

    # Phrase entiere centree verticalement
    lignes = couper_texte(caption, f_texte, ZONE)
    hauteur = len(lignes) * 90
    y = (H - hauteur) // 2

    for ligne in lignes:
        w = draw.textbbox((0, 0), ligne, font=f_texte)[2]
        draw.text(((W - w) / 2, y), ligne, font=f_texte, fill="white")
        y += 90

    # Branding
    draw.rectangle([60, H - 100, W - 60, H - 94], fill=palette["accent"])
    brand = "@PairAidantPeerSupport"
    w     = draw.textbbox((0, 0), brand, font=f_brand)[2]
    draw.text(((W - w) / 2, H - 82), brand, font=f_brand, fill="white")

    img.save(fichier_sortie, quality=95)
    print(f"Image creee : {fichier_sortie}")

# ─── Publication Facebook ─────────────────────────────────────────────────────

def publier(image_locale, caption, token):
    result    = cloudinary.uploader.upload(image_locale)
    image_url = result["secure_url"]
    print(f"Image uploadee : {image_url}")

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
    token   = renouveler_token()
    jft     = scraper_jft()
    caption = generer_caption(jft)
    creer_image(caption, "post.jpg")
    publier("post.jpg", caption, token)


if __name__ == "__main__":
    main()
