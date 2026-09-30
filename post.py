import os
import random
import base64
import glob
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import cloudinary
import cloudinary.uploader
from nacl import encoding, public

# ─── Config ───────────────────────────────────────────────────────────────────

FB_TOKEN         = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID       = os.environ["FB_PAGE_ID"]
GH_TOKEN         = os.environ["GH_TOKEN"]
REPO             = "mystofila/afder-auto-post"
JFT_URL          = "https://jpa.narcotiquesanonymes.org/"

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

# ─── Scraping JFT (français) ──────────────────────────────────────────────────

def scraper_jft():
    """Scrape jpa.narcotiquesanonymes.org — citation déjà en français, pas d'IA."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    r = requests.get(JFT_URL, timeout=15, headers=headers)
    r.raise_for_status()

    soup     = BeautifulSoup(r.text, "html.parser")
    cellules = [td.get_text(separator=" ", strip=True) for td in soup.find_all("td")]
    cellules = [c for c in cellules if len(c) > 3]

    if not cellules:
        cellules = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
        cellules = [c for c in cellules if len(c) > 20]

    if not cellules:
        body     = soup.get_text(separator="\n", strip=True)
        cellules = [l for l in body.split("\n") if len(l) > 20]

    print(f"Cellules extraites : {len(cellules)}")
    for i, c in enumerate(cellules):
        print(f"  [{i}] {c[:100]}")

    if not cellules:
        raise RuntimeError("Aucun contenu extrait du site JFT")

    quote = next((c for c in reversed(cellules) if "juste pour aujourd" in c.lower()), None)
    if not quote:
        quote = cellules[-1]

    print(f"Citation : {quote[:120]}")
    return quote.strip()


def generer_caption(caption_brute):
    """Nettoie et adapte la citation française : NA -> AFDER, refs religieuses -> laïc."""
    caption = caption_brute
    remplacements = [
        ("Narcotiques Anonymes", "AFDER"),
        ("narcotiques anonymes", "AFDER"),
        ("NA", "AFDER"),
        ("Dieu", "la communauté"),
        ("dieu", "la communauté"),
        ("puissance supérieure", "la force du collectif"),
        ("Puissance Supérieure", "la force du collectif"),
        ("puissances supérieures", "la force du collectif"),
        ("divinité", "l'entraide"),
    ]
    for ancien, nouveau in remplacements:
        caption = caption.replace(ancien, nouveau)

    if not caption.lower().startswith("juste pour aujourd"):
        caption = "Juste pour aujourd'hui : " + caption
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
    token         = renouveler_token()
    citation_brut = scraper_jft()
    caption       = generer_caption(citation_brut)
    print(f"Caption finale : {caption}")
    creer_image(caption, "post.jpg")
    publier("post.jpg", caption, token)


if __name__ == "__main__":
    main()
