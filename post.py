import os
import json
import random
import base64
import glob
import requests
from bs4 import BeautifulSoup
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

JFT_URL        = "https://www.jftna.org/jft/"

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
    print("Token longue durée activé et sauvegardé.")
    return nouveau_token


def _sauvegarder_secret_github(nom_secret, valeur):
    """Chiffre et sauvegarde une valeur dans les secrets GitHub Actions."""
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
    """
    Récupère la méditation du jour depuis jftna.org/jft/.

    Structure HTML de la page (stable depuis des années) :
      <table> contenant des <tr> successifs :
        - Date
        - Titre de la méditation
        - Thème / sous-titre
        - Citation principale (entre guillemets)
        - Texte de la méditation (plusieurs paragraphes)
        - Référence (ex: "Basic Text, p. 84")
        - "Just for today:" + pensée courte du jour

    Retourne un dict avec les clés :
        date, titre, theme, citation, texte, reference, jft
    """
    r    = requests.get(JFT_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Toutes les cellules de contenu sont dans des <td> de la table principale
    cellules = [td.get_text(separator=" ", strip=True) for td in soup.find_all("td")]
    # On filtre les cellules vides
    cellules = [c for c in cellules if c]

    print(f"Cellules extraites ({len(cellules)}) :")
    for i, c in enumerate(cellules):
        print(f"  [{i}] {c[:80]}")

    # Mapping par position — la page JFT a une structure fixe :
    # [0] date  [1] titre  [2] thème  [3] citation  [4..n-2] texte  [n-1] ref  [n] jft
    if len(cellules) < 5:
        raise ValueError(f"Structure JFT inattendue — seulement {len(cellules)} cellules")

    date      = cellules[0]
    titre     = cellules[1]
    theme     = cellules[2]
    citation  = cellules[3]
    # Le "Just for today:" final est souvent la dernière ou avant-dernière cellule
    jft_ligne = next((c for c in reversed(cellules) if c.lower().startswith("just for today")), "")
    reference = next((c for c in reversed(cellules) if "p." in c or "text" in c.lower()), "")
    # Le corps = tout ce qui est entre citation et reference/jft
    idx_debut = 4
    idx_fin   = len(cellules) - (2 if jft_ligne and reference else 1)
    texte     = " ".join(cellules[idx_debut:idx_fin]).strip()

    jft_data = {
        "date":      date,
        "titre":     titre,
        "theme":     theme,
        "citation":  citation,
        "texte":     texte,
        "reference": reference,
        "jft":       jft_ligne,
    }
    print(f"\nJFT extrait — Titre : {titre} | Thème : {theme}")
    return jft_data

# ─── Adaptation et génération du post ─────────────────────────────────────────

def generer_caption(jft_data):
    """
    Traduit et adapte la méditation JFT du jour en post Facebook AFDER.

    Règles d'adaptation :
    - "NA" / "Narcotiques Anonymes" → "AFDER" ou "notre association"
    - Toute mention de Dieu, divinité, puissance supérieure, Higher Power
      → "la force du collectif", "le soutien du groupe", "l'entraide"
    - Ton bienveillant, inclusif, non-religieux
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""Tu es un rédacteur bienveillant pour AFDER (Association Française des Dépendants en Rétablissement).
Voici la méditation "Juste pour aujourd'hui" du jour (en anglais) :

TITRE : {jft_data['titre']}
THÈME : {jft_data['theme']}
CITATION : {jft_data['citation']}
TEXTE : {jft_data['texte']}
PENSÉE DU JOUR : {jft_data['jft']}

Ta mission : créer un post Facebook en français, inspiré de cette méditation.

RÈGLES D'ADAPTATION OBLIGATOIRES :
1. Traduis et adapte librement — ne copie pas mot pour mot
2. Remplace toute mention de "NA", "Narcotics Anonymous", "Narcotiques Anonymes" par "AFDER" ou "notre association"
3. Remplace toute mention de "Dieu", "divinité", "puissance supérieure", "Higher Power", "God", "spiritual" par des formulations laïques : "la force du collectif", "le soutien du groupe", "l'entraide", "la communauté"
4. Garde le message d'espoir et de rétablissement

FORMAT DU POST :
- UNE phrase d'accroche forte (max 12 mots)
- UNE phrase de corps (max 15 mots, phrase COMPLÈTE avec point final)
- La pensée du jour adaptée : "Juste pour aujourd'hui : [max 12 mots]"
- 3 hashtags français pertinents
- Pas d'emoji
- Réponds UNIQUEMENT avec le texte du post, rien d'autre"""

    reponse = client.models.generate_content(model="gemma-3-27b-it", contents=prompt)
    caption = reponse.text.strip()
    print(f"\nCaption générée :\n{caption}")
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
    W, H    = 1080, 1080
    MARGE   = 80
    ZONE    = W - (MARGE * 2)
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
        f_corps    = ImageFont.truetype(FONT_REGULAR, 52)
        f_jft      = ImageFont.truetype(FONT_REGULAR, 44)
        f_brand    = ImageFont.truetype(FONT_BOLD,    34)
    except Exception:
        f_accroche = f_corps = f_jft = f_brand = ImageFont.load_default()

    # Logo
    if logo:
        try:
            img_logo = Image.open(logo).convert("RGBA")
            img_logo = img_logo.resize((120, 120))
            img.paste(img_logo, (MARGE, 40), img_logo)
        except Exception as e:
            print(f"Erreur logo : {e}")

    # Découpage du texte :
    # ligne 1 = accroche (avant le premier ".")
    # ligne 2 = corps (entre le 1er et 2ème ".")
    # ligne 3 = "Juste pour aujourd'hui : ..." (commence par "Juste")
    lignes_brutes = [l.strip() for l in caption.split("\n") if l.strip()]
    hashtags = " ".join([l for l in lignes_brutes if l.startswith("#")])
    contenu  = [l for l in lignes_brutes if not l.startswith("#")]

    accroche  = contenu[0] if len(contenu) > 0 else ""
    corps     = contenu[1] if len(contenu) > 1 else ""
    jft_ligne = next((l for l in contenu if "juste pour" in l.lower()), "")
    if not jft_ligne and len(contenu) > 2:
        jft_ligne = contenu[2]

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

    y = 200

    # Accroche
    for ligne in couper_texte(accroche, f_accroche, ZONE)[:3]:
        w = draw.textbbox((0, 0), ligne, font=f_accroche)[2]
        draw.text(((W - w) / 2, y), ligne, font=f_accroche, fill="white")
        y += 78

    # Séparateur
    draw.rectangle([(W - 120) / 2, y + 12, (W + 120) / 2, y + 20], fill=palette["accent"])
    y += 58

    # Corps
    if corps:
        for ligne in couper_texte(corps, f_corps, ZONE)[:4]:
            w = draw.textbbox((0, 0), ligne, font=f_corps)[2]
            draw.text(((W - w) / 2, y), ligne, font=f_corps, fill=(210, 225, 255))
            y += 62

    # "Juste pour aujourd'hui"
    if jft_ligne:
        y += 20
        draw.rectangle([(W - 120) / 2, y, (W + 120) / 2, y + 2], fill=palette["accent"])
        y += 20
        for ligne in couper_texte(jft_ligne, f_jft, ZONE)[:3]:
            w = draw.textbbox((0, 0), ligne, font=f_jft)[2]
            draw.text(((W - w) / 2, y), ligne, font=f_jft, fill=(255, 220, 160))
            y += 54

    # Branding
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
    token   = renouveler_token()
    jft     = scraper_jft()
    caption = generer_caption(jft)
    creer_image(caption, "post.jpg")
    publier("post.jpg", caption, token)


if __name__ == "__main__":
    main()
