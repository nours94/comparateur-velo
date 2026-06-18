import os
import re
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
VELO_TABLE_NAME = os.getenv("VELO_TABLE_NAME", "vélo")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL introuvable.")

engine = create_engine(DATABASE_URL)

HEADERS = {
    "User-Agent": "Mozilla/5.0 VéloÉlecBot/1.0",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

URLS_CATEGORIES = [
    "https://www.decathlon.fr/tous-les-sports/velo-cyclisme/velos-electriques",
    "https://www.decathlon.fr/tous-les-sports/velo-cyclisme/velos-cargo-electriques",
    "https://www.decathlon.fr/tous-les-sports/velo-cyclisme/velos-ville-electriques",
    "https://www.decathlon.fr/tous-les-sports/velo-cyclisme/vtt-electriques",
    "https://www.decathlon.fr/tous-les-sports/velo-cyclisme/vtc-electriques",
]


def nettoyer_texte(valeur):
    if not valeur:
        return ""
    return re.sub(r"\s+", " ", str(valeur)).strip()


def extraire_nombre(texte):
    if not texte:
        return None
    match = re.search(r"(\d+(?:[,.]\d+)?)", texte)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def extraire_prix(texte):
    if not texte:
        return 0
    texte = texte.replace("\xa0", " ")
    match = re.search(r"(\d+(?:[ .]\d{3})*(?:[,.]\d+)?)\s*€", texte)
    if not match:
        return 0
    prix = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    return int(float(prix))


def extraire_couple(texte):
    match = re.search(r"(\d+)\s*nm", texte.lower())
    return int(match.group(1)) if match else None


def extraire_batterie_wh(texte):
    match = re.search(r"(\d+)\s*wh", texte.lower())
    return f"{match.group(1)} Wh" if match else ""


def extraire_autonomie(texte):
    match = re.search(r"jusqu.?à\s*(\d+)\s*km", texte.lower())
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*km\s*d.autonomie", texte.lower())
    return int(match.group(1)) if match else None


def extraire_poids(texte):
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*kg", texte.lower())
    return float(match.group(1).replace(",", ".")) if match else None


def generer_identifiant(url, nom):
    base = url or nom
    h = hashlib.md5(base.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")
    return f"decathlon-{slug[:45]}-{h}"


def recuperer_liens_produits():
    liens = set()

    for url in URLS_CATEGORIES:
        print(f"Recherche catégorie : {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200:
                print(f"Erreur catégorie {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]

                if "/p/" in href:
                    if href.startswith("/"):
                        href = "https://www.decathlon.fr" + href
                    if "decathlon.fr" in href:
                        liens.add(href.split("?")[0])

            time.sleep(1)

        except Exception as e:
            print(f"Erreur récupération catégorie : {e}")

    return list(liens)


def analyser_fiche_produit(url):
    print(f"Analyse produit : {url}")

    response = requests.get(url, headers=HEADERS, timeout=25)
    if response.status_code != 200:
        print(f"Produit ignoré, statut {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    texte_page = nettoyer_texte(soup.get_text(" "))

    title = soup.find("h1")
    nom = nettoyer_texte(title.get_text()) if title else ""

    if not nom:
        meta_title = soup.find("meta", property="og:title")
        nom = nettoyer_texte(meta_title.get("content")) if meta_title else ""

    if not nom:
        return None

    nom_lower = nom.lower()
    page_lower = texte_page.lower()

    if "électrique" not in page_lower and "electrique" not in page_lower and "e-bike" not in page_lower:
        return None

    image_url = ""
    meta_img = soup.find("meta", property="og:image")
    if meta_img:
        image_url = meta_img.get("content", "")

    prix = extraire_prix(texte_page)
    couple = extraire_couple(texte_page)
    batterie = extraire_batterie_wh(texte_page)
    autonomie = extraire_autonomie(texte_page)
    poids = extraire_poids(texte_page)

    categorie = "Vélo électrique"
    if "cargo" in page_lower or "longtail" in page_lower:
        categorie = "Vélo cargo électrique"
    elif "vtt" in page_lower or "rockrider" in page_lower:
        categorie = "VTT électrique"
    elif "vtc" in page_lower:
        categorie = "VTC électrique"
    elif "ville" in page_lower:
        categorie = "Vélo ville électrique"

    marque = "Decathlon"
    if "rockrider" in nom_lower:
        marque = "Rockrider"
    elif "btwin" in nom_lower or "b'twin" in nom_lower:
        marque = "Btwin"
    elif "elops" in nom_lower:
        marque = "Elops"
    elif "riverside" in nom_lower:
        marque = "Riverside"

    moteur = ""
    moteur_match = re.search(r"(moteur[^.]{0,120})", texte_page, re.IGNORECASE)
    if moteur_match:
        moteur = nettoyer_texte(moteur_match.group(1))

    if couple and "nm" not in moteur.lower():
        moteur = f"{moteur} {couple} Nm".strip()

    description = f"Vélo importé depuis Decathlon France. Catégorie : {categorie}."
    if couple:
        description += f" Couple moteur : {couple} Nm."
    if batterie:
        description += f" Batterie : {batterie}."
    if autonomie:
        description += f" Autonomie annoncée : jusqu'à {autonomie} km."

    return {
        "identifiant": generer_identifiant(url, nom),
        "nom": nom,
        "prix": prix,
        "moteur": moteur,
        "batterie": batterie,
        "description_ia": description,
        "image_url": image_url,
        "marque": marque,
        "modele": nom,
        "marque_moteur": "",
        "couple_moteur": couple,
        "moteur_energie": None,
        "autonomie": autonomie,
        "categorie": categorie,
        "poids": poids,
        "taille_min": None,
        "taille_max": None,
    }


def upsert_velo(velo):
    sql = text(f"""
        INSERT INTO "{VELO_TABLE_NAME}" (
            identifiant,
            nom,
            prix,
            moteur,
            batterie,
            description_ia,
            "URL de l'image",
            marque,
            "modèle",
            marque_moteur,
            couple_moteur,
            "moteur d'énergie",
            autonomie,
            "catégorie",
            poids,
            taille_min,
            taille_max
        )
        VALUES (
            :identifiant,
            :nom,
            :prix,
            :moteur,
            :batterie,
            :description_ia,
            :image_url,
            :marque,
            :modele,
            :marque_moteur,
            :couple_moteur,
            :moteur_energie,
            :autonomie,
            :categorie,
            :poids,
            :taille_min,
            :taille_max
        )
        ON CONFLICT (identifiant)
        DO UPDATE SET
            nom = EXCLUDED.nom,
            prix = EXCLUDED.prix,
            moteur = EXCLUDED.moteur,
            batterie = EXCLUDED.batterie,
            description_ia = EXCLUDED.description_ia,
            "URL de l'image" = EXCLUDED."URL de l'image",
            marque = EXCLUDED.marque,
            "modèle" = EXCLUDED."modèle",
            marque_moteur = EXCLUDED.marque_moteur,
            couple_moteur = EXCLUDED.couple_moteur,
            "moteur d'énergie" = EXCLUDED."moteur d'énergie",
            autonomie = EXCLUDED.autonomie,
            "catégorie" = EXCLUDED."catégorie",
            poids = EXCLUDED.poids,
            taille_min = EXCLUDED.taille_min,
            taille_max = EXCLUDED.taille_max;
    """)

    with engine.begin() as conn:
        conn.execute(sql, velo)


def main():
    liens = recuperer_liens_produits()
    print(f"{len(liens)} fiches produits trouvées.")

    ajoutes = 0
    ignores = 0

    for lien in liens:
        try:
            velo = analyser_fiche_produit(lien)

            if not velo:
                ignores += 1
                continue

            upsert_velo(velo)
            ajoutes += 1
            print(f"OK : {velo['nom']}")

            time.sleep(1.5)

        except Exception as e:
            ignores += 1
            print(f"Erreur produit : {e}")

    print("Import terminé.")
    print(f"Vélos ajoutés ou mis à jour : {ajoutes}")
    print(f"Produits ignorés : {ignores}")


if __name__ == "__main__":
    main()