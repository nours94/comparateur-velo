import os
import re
import time
import logging
import hashlib
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("robot_chargement_vef.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("robot_chargement_vef")

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
VELO_TABLE_NAME = os.getenv("VELO_TABLE_NAME", "velos")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL introuvable.")

engine = create_engine(DATABASE_URL)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Source : VeloElectriqueFrance.fr — sous-catégories par type de vélo,
# associées à la "categorie" qu'on enregistrera en base.
URLS_CATEGORIES = {
    "https://www.veloelectriquefrance.fr/15-velo-electrique-de-ville": "Vélo ville électrique",
    "https://www.veloelectriquefrance.fr/216-velo-electrique-cargo-et-triporteur": "Vélo cargo électrique",
    "https://www.veloelectriquefrance.fr/14-velo-electrique-pliant": "Vélo électrique pliant",
    "https://www.veloelectriquefrance.fr/16-vtt-electrique": "VTT électrique",
    "https://www.veloelectriquefrance.fr/269-vtc-tout-terrain": "VTC électrique",
    "https://www.veloelectriquefrance.fr/327-velo-electrique-long-taille": "Vélo cargo électrique",
}

# Nombre de pages de pagination à parcourir par catégorie (sécurité anti-boucle infinie)
MAX_PAGES_PAR_CATEGORIE = 10

PRIX_MIN_VALIDE = 300
PRIX_MAX_VALIDE = 15000
POIDS_MIN_VALIDE = 8.0
POIDS_MAX_VALIDE = 45.0


# -------------------------------------------------------------------------
# OUTILS DE NETTOYAGE
# -------------------------------------------------------------------------
def nettoyer_texte(valeur):
    if not valeur:
        return ""
    return re.sub(r"\s+", " ", str(valeur)).strip()


def extraire_prix(texte):
    if not texte:
        return 0
    texte = texte.replace("\xa0", " ")
    match = re.search(r"(\d+(?:[ .]\d{3})*(?:[,.]\d+)?)\s*€", texte)
    if not match:
        return 0
    prix = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return int(float(prix))
    except ValueError:
        return 0


def extraire_nombre(texte):
    if not texte:
        return None
    match = re.search(r"(\d+(?:[,.]\d+)?)", texte.replace("\xa0", " "))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def generer_identifiant(url, nom):
    base = url or nom
    h = hashlib.md5(base.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")
    return f"vef-{slug[:45]}-{h}"


# -------------------------------------------------------------------------
# VALIDATION
# -------------------------------------------------------------------------
def valider_velo(velo: dict) -> tuple[bool, list[str]]:
    raisons_rejet = []

    if not velo.get("nom") or len(velo["nom"]) < 3:
        raisons_rejet.append("nom manquant ou trop court")

    prix = velo.get("prix") or 0
    if prix < PRIX_MIN_VALIDE or prix > PRIX_MAX_VALIDE:
        raisons_rejet.append(
            f"prix hors plage plausible ({prix}€, attendu entre "
            f"{PRIX_MIN_VALIDE}€ et {PRIX_MAX_VALIDE}€)"
        )

    poids = velo.get("poids")
    if poids is not None and (poids < POIDS_MIN_VALIDE or poids > POIDS_MAX_VALIDE):
        raisons_rejet.append(
            f"poids hors plage plausible ({poids} kg, attendu entre "
            f"{POIDS_MIN_VALIDE} et {POIDS_MAX_VALIDE} kg)"
        )

    if not velo.get("identifiant"):
        raisons_rejet.append("identifiant non généré")

    return (len(raisons_rejet) == 0, raisons_rejet)


# -------------------------------------------------------------------------
# RÉCUPÉRATION DES LIENS PRODUITS (avec catégorie associée)
# -------------------------------------------------------------------------
def recuperer_liens_produits():
    """Retourne une liste de tuples (url_produit, categorie_associee)."""
    liens_avec_categorie = {}

    for url_categorie, nom_categorie in URLS_CATEGORIES.items():
        logger.info(f"Recherche catégorie : {url_categorie} ({nom_categorie})")

        for page in range(1, MAX_PAGES_PAR_CATEGORIE + 1):
            url_page = url_categorie if page == 1 else f"{url_categorie}?page={page}"

            try:
                response = requests.get(url_page, headers=HEADERS, timeout=20)

                if response.status_code != 200:
                    logger.warning(
                        f"  Statut HTTP {response.status_code} pour {url_page} -> arrêt pagination"
                    )
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # Liens produits : se terminent par un .html, contiennent un ID numérique
                liens_page = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if re.search(r"/\d+-[a-z0-9-]+\.html", href, re.IGNORECASE):
                        if href.startswith("/"):
                            href = "https://www.veloelectriquefrance.fr" + href
                        liens_page.add(href.split("#")[0].split("?")[0])

                nouveaux = liens_page - set(liens_avec_categorie.keys())
                for lien in nouveaux:
                    liens_avec_categorie[lien] = nom_categorie

                logger.info(f"  Page {page} : {len(nouveaux)} nouveaux liens")

                if not nouveaux:
                    break

                time.sleep(1.5)

            except requests.RequestException as e:
                logger.error(f"  Erreur réseau sur {url_page} : {e}")
                break
            except Exception as e:
                logger.error(f"  Erreur inattendue sur {url_page} : {e}")
                break

    logger.info(f"Total liens produits uniques collectés : {len(liens_avec_categorie)}")
    return list(liens_avec_categorie.items())


# -------------------------------------------------------------------------
# ANALYSE D'UNE FICHE PRODUIT
# -------------------------------------------------------------------------
def analyser_fiche_produit(url, categorie_connue):
    logger.info(f"Analyse produit : {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException as e:
        logger.error(f"  Erreur réseau : {e}")
        return None

    if response.status_code != 200:
        logger.warning(f"  Produit ignoré, statut HTTP {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # --- Nom du produit ---
    title_tag = soup.find("h1")
    nom = nettoyer_texte(title_tag.get_text()) if title_tag else ""
    if not nom:
        meta_title = soup.find("meta", property="og:title")
        nom = nettoyer_texte(meta_title.get("content")) if meta_title else ""
    if not nom:
        logger.warning("  Produit ignoré : impossible d'extraire un nom")
        return None

    nom_lower = nom.lower()

    if "occasion" in nom_lower:
        logger.info(f"  Produit ignoré (occasion) : {nom}")
        return None

    # --- Image ---
    image_url = ""
    meta_img = soup.find("meta", property="og:image")
    if meta_img:
        image_url = meta_img.get("content", "")

    # --- Prix : priorité aux balises meta structurées ---
    prix = 0
    meta_price = soup.find("meta", property="product:price:amount")
    if meta_price and meta_price.get("content"):
        try:
            prix = int(float(meta_price.get("content")))
        except (ValueError, TypeError):
            prix = 0
    if not prix:
        prix_tag = soup.find(attrs={"class": re.compile("price", re.IGNORECASE)})
        if prix_tag:
            prix = extraire_prix(prix_tag.get_text())

    # --- Marque : via schema.org si présent, sinon déduite du nom ---
    marque = ""
    meta_brand = soup.find(attrs={"itemprop": "brand"})
    if meta_brand:
        marque = nettoyer_texte(meta_brand.get("content") or meta_brand.get_text())
    if not marque:
        marques_connues = [
            "gitane", "peugeot", "beaufort", "ahooga", "grandville", "tenways",
            "eovolt", "conor", "fitch", "cycle denis", "voltaire", "bottecchia",
            "kalkhoff", "superior", "rock machine", "sunn", "myland", "t-bird",
        ]
        for candidat in marques_connues:
            if candidat in nom_lower:
                marque = candidat.title()
                break

    # --- Fiche technique : VeloElectriqueFrance utilise des <div class="coloroff">
    # contenant directement "Label : Valeur" en texte, à l'intérieur d'un <table>
    # (ex: <div class="coloroff">Batterie : 400W</div>), pas une vraie colonne de table.
    fiche = {}
    description_div = soup.find(class_="ce-product-description")
    if description_div:
        for div in description_div.find_all("div"):
            texte_div = nettoyer_texte(div.get_text())
            if ":" in texte_div:
                label, _, valeur = texte_div.partition(":")
                label = label.strip().lower()
                valeur = valeur.strip()
                if label and valeur and len(label) < 40:
                    fiche[label] = valeur

    # Fallback générique : vraie structure de table en 2 colonnes (au cas où)
    if not fiche:
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cellules = row.find_all(["th", "td"])
                if len(cellules) == 2:
                    label = nettoyer_texte(cellules[0].get_text()).lower()
                    valeur = nettoyer_texte(cellules[1].get_text())
                    if label:
                        fiche[label] = valeur

    def valeur_fiche(*cles):
        for cle in cles:
            for cle_fiche, val in fiche.items():
                if cle in cle_fiche:
                    return val
        return None

    # --- Description complète pour extraction par regex (fallback) ---
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description_meta = nettoyer_texte(meta_desc.get("content")) if meta_desc else ""
    texte_complet_lower = f"{nom} {description_meta}".lower()

    # --- Marque moteur ---
    marque_moteur = valeur_fiche("marque du moteur", "moteur") or ""
    if not marque_moteur:
        for candidat in ["bosch", "shimano", "bafang", "brose", "yamaha", "ananda", "mivice"]:
            if candidat in texte_complet_lower:
                marque_moteur = candidat.capitalize()
                break

    # --- Couple moteur (Nm) ---
    couple_brut = valeur_fiche("couple")
    couple_moteur = int(extraire_nombre(couple_brut)) if couple_brut else None
    if not couple_moteur:
        match_couple = re.search(r"(\d{1,3})\s*nm", texte_complet_lower)
        if match_couple:
            couple_moteur = int(match_couple.group(1))

    # --- Puissance moteur (W) ---
    energie_moteur = None
    match_w = re.search(r"(\d{2,4})\s*w(?:att)?s?\b", texte_complet_lower)
    if match_w:
        valeur_w = int(match_w.group(1))
        if 100 <= valeur_w <= 1000:
            energie_moteur = valeur_w

    # --- Batterie (Wh, ou parfois noté simplement W sur ce site) ---
    batterie_brut = valeur_fiche("capacité batterie", "batterie")
    batterie = batterie_brut or ""
    if not batterie:
        match_wh = re.search(r"(\d{2,4})\s*wh\b", texte_complet_lower)
        if match_wh:
            batterie = f"{match_wh.group(1)} Wh"

    # --- Poids (kg) ---
    poids_brut = valeur_fiche("poids")
    poids = extraire_nombre(poids_brut) if poids_brut else None
    if not poids:
        match_poids = re.search(r"(\d{1,2}[,.]\d{1,2})\s*kg", texte_complet_lower)
        if match_poids:
            poids = float(match_poids.group(1).replace(",", "."))

    description = f"Vélo importé depuis VeloElectriqueFrance. Catégorie : {categorie_connue}."
    if couple_moteur:
        description += f" Couple moteur : {couple_moteur} Nm."
    if energie_moteur:
        description += f" Puissance moteur : {energie_moteur} W."
    if batterie:
        description += f" Batterie : {batterie}."
    if description_meta:
        description += f" {description_meta}"

    velo = {
        "identifiant": generer_identifiant(url, nom),
        "nom": nom,
        "prix": prix,
        "moteur": marque_moteur,
        "batterie": batterie,
        "description_ia": description,
        "image_url": image_url,
        "marque": marque,
        "modele": nom,
        "marque_moteur": marque_moteur,
        "couple_moteur": couple_moteur,
        "energie_moteur": energie_moteur,
        "autonomie": None,
        "categorie": categorie_connue,
        "poids": poids,
        "taille_min": None,
        "taille_max": None,
    }

    logger.info(
        f"  Extraction réussie : nom='{nom}', prix={prix}€, marque={marque}, marque_moteur={marque_moteur}, "
        f"couple={couple_moteur}Nm, energie={energie_moteur}W, batterie={batterie}, poids={poids}kg"
    )

    return velo


# -------------------------------------------------------------------------
# INSERTION / MISE À JOUR EN BASE (UPSERT)
# -------------------------------------------------------------------------
def upsert_velo(velo: dict):
    sql = text(f"""
        INSERT INTO "{VELO_TABLE_NAME}" (
            id,
            nom,
            prix,
            moteur,
            batterie,
            description_ia,
            image_url,
            marque,
            modele,
            marque_moteur,
            couple_moteur,
            energie_moteur,
            autonomie,
            categorie,
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
            :energie_moteur,
            :autonomie,
            :categorie,
            :poids,
            :taille_min,
            :taille_max
        )
        ON CONFLICT (id)
        DO UPDATE SET
            nom = EXCLUDED.nom,
            prix = EXCLUDED.prix,
            moteur = EXCLUDED.moteur,
            batterie = EXCLUDED.batterie,
            description_ia = EXCLUDED.description_ia,
            image_url = EXCLUDED.image_url,
            marque = EXCLUDED.marque,
            modele = EXCLUDED.modele,
            marque_moteur = EXCLUDED.marque_moteur,
            couple_moteur = EXCLUDED.couple_moteur,
            energie_moteur = EXCLUDED.energie_moteur,
            autonomie = EXCLUDED.autonomie,
            categorie = EXCLUDED.categorie,
            poids = EXCLUDED.poids,
            taille_min = EXCLUDED.taille_min,
            taille_max = EXCLUDED.taille_max;
    """)

    with engine.begin() as conn:
        conn.execute(sql, velo)


# -------------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# -------------------------------------------------------------------------
def main():
    logger.info("=" * 70)
    logger.info("Démarrage du robot de chargement VeloElectriqueFrance")
    logger.info("=" * 70)

    liens = recuperer_liens_produits()
    logger.info(f"{len(liens)} fiches produits trouvées au total.")

    # --- Mode test désactivé : import complet sur tous les liens collectés ---

    stats = {
        "inseres_ou_maj": 0,
        "rejetes_validation": 0,
        "ignores_non_velo_elec": 0,
        "erreurs": 0,
    }
    details_rejets = []

    for lien, categorie_connue in liens:
        try:
            velo = analyser_fiche_produit(lien, categorie_connue)

            if not velo:
                stats["ignores_non_velo_elec"] += 1
                continue

            est_valide, raisons = valider_velo(velo)

            if not est_valide:
                stats["rejetes_validation"] += 1
                message_rejet = f"REJETÉ '{velo.get('nom', '?')}' ({lien}) : {', '.join(raisons)}"
                logger.warning(f"  {message_rejet}")
                details_rejets.append(message_rejet)
                continue

            upsert_velo(velo)
            stats["inseres_ou_maj"] += 1
            logger.info(f"  OK -> inséré/mis à jour : {velo['nom']}")

            time.sleep(1.5)

        except Exception as e:
            stats["erreurs"] += 1
            logger.error(f"Erreur inattendue sur {lien} : {e}")

    logger.info("=" * 70)
    logger.info("RÉSUMÉ DE L'IMPORT")
    logger.info("=" * 70)
    logger.info(f"Vélos insérés ou mis à jour : {stats['inseres_ou_maj']}")
    logger.info(f"Rejetés après validation     : {stats['rejetes_validation']}")
    logger.info(f"Ignorés (non vélo électrique): {stats['ignores_non_velo_elec']}")
    logger.info(f"Erreurs techniques           : {stats['erreurs']}")

    if details_rejets:
        logger.info("-" * 70)
        logger.info("Détail des rejets (validation) :")
        for d in details_rejets:
            logger.info(f"  - {d}")

    logger.info("Import terminé.")


if __name__ == "__main__":
    main()
