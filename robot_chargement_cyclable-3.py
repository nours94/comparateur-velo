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
        logging.FileHandler("robot_chargement.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("robot_chargement")

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
VELO_TABLE_NAME = os.getenv("VELO_TABLE_NAME", "velos")  # nom réel de la table

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

# Source : Cyclable.com — catalogue complet des vélos à assistance électrique
URLS_CATEGORIES = [
    "https://www.cyclable.com/183-velo-electrique-ville",       # Vélo électrique ville
    "https://www.cyclable.com/294-vtc-electrique",                # VTC électrique
    "https://www.cyclable.com/946-vtt-electrique",                # VTT électrique
    "https://www.cyclable.com/1326-velo-cargo-electrique",        # Vélo cargo électrique
    "https://www.cyclable.com/1352-velo-randonnee-electrique",    # Vélo randonnée électrique
    "https://www.cyclable.com/268-velo-electrique-pliant",        # Vélo électrique pliant
]

# Nombre de pages de pagination à parcourir par catégorie (sécurité anti-boucle infinie)
MAX_PAGES_PAR_CATEGORIE = 10

# Seuils de validation (à ajuster selon ton marché)
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
    """Extrait un prix au format '1 699,00 €' -> 1699"""
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
    """Extrait le premier nombre (entier ou décimal) d'une chaîne."""
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
    return f"cyclable-{slug[:45]}-{h}"


# -------------------------------------------------------------------------
# VALIDATION DES DONNÉES AVANT INSERTION
# -------------------------------------------------------------------------
def valider_velo(velo: dict) -> tuple[bool, list[str]]:
    """
    Vérifie qu'une fiche vélo extraite est suffisamment fiable pour être
    insérée en base. Retourne (est_valide, liste_des_raisons_de_rejet).
    """
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
# RÉCUPÉRATION DES LIENS PRODUITS (avec pagination)
# -------------------------------------------------------------------------
def recuperer_liens_produits():
    liens = set()

    for url_categorie in URLS_CATEGORIES:
        logger.info(f"Recherche catégorie : {url_categorie}")

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

                # La page catégorie Cyclable est construite avec Elementor :
                # chaque carte produit est un <article data-id-product="19212">.
                # On cherche le VRAI lien <a href="...slug...html"> à l'intérieur
                # de la carte (l'URL sans slug retourne une 404 sur ce PrestaShop).
                articles = soup.find_all(attrs={"data-id-product": True})

                liens_page = set()
                for article in articles:
                    id_produit = article.get("data-id-product")
                    if not id_produit or not id_produit.isdigit():
                        continue

                    # On exclut les vélos d'occasion en vérifiant le nom affiché
                    titre_tag = article.find(class_="ce-product-name")
                    nom_carte = titre_tag.get_text(strip=True).lower() if titre_tag else ""
                    if "occasion" in nom_carte:
                        continue

                    # Cherche un href contenant l'ID produit suivi d'un tiret et .html
                    url_produit = None
                    for a in article.find_all("a", href=True):
                        href = a["href"]
                        if re.search(rf"/{id_produit}-[a-z0-9-]+\.html", href, re.IGNORECASE):
                            if href.startswith("/"):
                                href = "https://www.cyclable.com" + href
                            url_produit = href.split("?")[0]
                            break

                    # Repli : si aucun lien complet trouvé, on tente l'ID seul
                    # (peut fonctionner sur certaines configs PrestaShop)
                    if not url_produit:
                        url_produit = f"https://www.cyclable.com/{id_produit}.html"

                    liens_page.add(url_produit)

                nouveaux = liens_page - liens
                liens.update(nouveaux)

                logger.info(f"  Page {page} : {len(nouveaux)} nouveaux liens (total catégorie en cours)")

                # Si la page ne ramène aucun nouveau lien, on arrête la pagination
                if not nouveaux:
                    break

                time.sleep(1.5)

            except requests.RequestException as e:
                logger.error(f"  Erreur réseau sur {url_page} : {e}")
                break
            except Exception as e:
                logger.error(f"  Erreur inattendue sur {url_page} : {e}")
                break

    logger.info(f"Total liens produits uniques collectés : {len(liens)}")
    return list(liens)


# -------------------------------------------------------------------------
# EXTRACTION DE LA FICHE TECHNIQUE STRUCTURÉE
# -------------------------------------------------------------------------
def extraire_fiche_technique(soup):
    """
    La page produit Cyclable contient une section 'Fiche technique' composée
    de paires label/valeur (ex: 'Couple moteur (Nm)' -> '75 Nm').
    On la retourne sous forme de dict {label_normalise: valeur_brute}.
    """
    fiche = {}

    # Cyclable structure ses caractéristiques avec des dl/dt/dd ou des divs
    # avec une classe contenant "data-sheet" / "feature". On essaie plusieurs
    # sélecteurs pour être robuste aux variations de template.
    candidats = soup.select("dl.data-sheet dt, dl.data-sheet dd")
    if candidats:
        dts = soup.select("dl.data-sheet dt")
        dds = soup.select("dl.data-sheet dd")
        for dt, dd in zip(dts, dds):
            label = nettoyer_texte(dt.get_text()).lower()
            valeur = nettoyer_texte(dd.get_text())
            if label:
                fiche[label] = valeur
        return fiche

    # Fallback générique : table de caractéristiques
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cellules = row.find_all(["th", "td"])
            if len(cellules) == 2:
                label = nettoyer_texte(cellules[0].get_text()).lower()
                valeur = nettoyer_texte(cellules[1].get_text())
                if label:
                    fiche[label] = valeur

    return fiche


def valeur_fiche(fiche, *cles_possibles):
    """Cherche la première clé correspondante (insensible à la casse/accents partiels) dans la fiche technique."""
    for cle in cles_possibles:
        for cle_fiche, valeur in fiche.items():
            if cle in cle_fiche:
                return valeur
    return None


# -------------------------------------------------------------------------
# ANALYSE D'UNE FICHE PRODUIT
# -------------------------------------------------------------------------
def analyser_fiche_produit(url):
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

    # Sécurité supplémentaire : on exclut aussi tout produit explicitement
    # marqué "occasion" dans son titre, même si l'URL ne le signalait pas.
    if "occasion" in nom_lower:
        logger.info(f"  Produit ignoré (occasion) : {nom}")
        return None

    # On ne garde que les produits réellement électriques
    if "électrique" not in nom_lower and "electrique" not in nom_lower and "e-bike" not in nom_lower:
        logger.info(f"  Produit ignoré (nom ne mentionne pas l'électrique) : {nom}")
        return None

    # --- Image ---
    image_url = ""
    meta_img = soup.find("meta", property="og:image")
    if meta_img:
        image_url = meta_img.get("content", "")

    # --- Prix ---
    # Cyclable expose le prix dans une balise meta structurée et fiable :
    # <meta property="product:price:amount" content="2499">
    prix = 0
    meta_price = soup.find("meta", property="product:price:amount")
    if meta_price and meta_price.get("content"):
        try:
            prix = int(float(meta_price.get("content")))
        except (ValueError, TypeError):
            prix = 0

    # Fallback : classe CSS contenant "price" si la balise meta est absente
    if not prix:
        prix_tag = soup.find(attrs={"class": re.compile("price", re.IGNORECASE)})
        if prix_tag:
            prix = extraire_prix(prix_tag.get_text())

    # --- Marque ---
    # Cyclable expose la marque via les données structurées schema.org :
    # <meta itemprop="brand" content="Riese & Muller">
    marque = ""
    meta_brand = soup.find(attrs={"itemprop": "brand"})
    if meta_brand:
        marque = nettoyer_texte(meta_brand.get("content") or meta_brand.get_text())

    # Fallback : déduction depuis le nom si la donnée structurée est absente
    if not marque:
        marques_connues = [
            "sunn", "winora", "moustache", "kalkhoff", "o2feel", "tenways", "yuba",
            "brompton", "gazelle", "riese", "tern", "uto", "eovolt", "btwin",
            "rockrider", "elops", "riverside", "bullitt", "triobike", "ritmic",
        ]
        for candidat in marques_connues:
            if candidat in nom_lower:
                marque = candidat.capitalize()
                break

    # --- SKU (référence produit, utile pour détecter l'occasion via le code) ---
    sku = ""
    meta_sku = soup.find(attrs={"itemprop": "sku"})
    if meta_sku:
        sku = nettoyer_texte(meta_sku.get("content") or meta_sku.get_text())

    if "occasion" in sku.lower():
        logger.info(f"  Produit ignoré (occasion détectée via SKU '{sku}') : {nom}")
        return None

    # --- Fiche technique structurée ---
    fiche = extraire_fiche_technique(soup)

    marque_moteur = valeur_fiche(fiche, "marque du moteur") or ""
    moteur = valeur_fiche(fiche, "moteur") or ""

    couple_brut = valeur_fiche(fiche, "couple moteur")
    couple_moteur = int(extraire_nombre(couple_brut)) if couple_brut else None

    # La puissance (W) est généralement dans la description du champ "Moteur"
    # ex: "Ananda M60, 250 W / 36 V, ..."
    energie_moteur = None
    if moteur:
        match_w = re.search(r"(\d{2,4})\s*w\b", moteur.lower())
        if match_w:
            energie_moteur = int(match_w.group(1))

    batterie_brut = valeur_fiche(fiche, "capacité batterie", "capacite batterie")
    batterie = batterie_brut or ""

    poids_brut = valeur_fiche(fiche, "poids")
    poids = extraire_nombre(poids_brut) if poids_brut else None

    # Catégorie déduite du nom du produit
    categorie = "Vélo électrique"
    if "cargo" in nom_lower:
        categorie = "Vélo cargo électrique"
    elif "vtt" in nom_lower:
        categorie = "VTT électrique"
    elif "vtc" in nom_lower:
        categorie = "VTC électrique"
    elif "pliant" in nom_lower:
        categorie = "Vélo électrique pliant"
    elif "randonnée" in nom_lower or "randonnee" in nom_lower:
        categorie = "Vélo randonnée électrique"
    elif "ville" in nom_lower:
        categorie = "Vélo ville électrique"

    # Description courte (meta description, déjà rédigée par Cyclable)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description_source = nettoyer_texte(meta_desc.get("content")) if meta_desc else ""

    description = f"Vélo importé depuis Cyclable. Catégorie : {categorie}."
    if couple_moteur:
        description += f" Couple moteur : {couple_moteur} Nm."
    if energie_moteur:
        description += f" Puissance moteur : {energie_moteur} W."
    if batterie:
        description += f" Batterie : {batterie}."
    if description_source:
        description += f" {description_source}"

    velo = {
        "identifiant": generer_identifiant(url, nom),
        "nom": nom,
        "prix": prix,
        "moteur": moteur,
        "batterie": batterie,
        "description_ia": description,
        "image_url": image_url,
        "marque": marque,
        "modele": nom,
        "marque_moteur": marque_moteur,
        "couple_moteur": couple_moteur,
        "energie_moteur": energie_moteur,
        "autonomie": None,  # Cyclable n'affiche généralement pas l'autonomie en fiche technique
        "categorie": categorie,
        "poids": poids,
        "taille_min": None,
        "taille_max": None,
    }

    logger.info(
        f"  Extraction réussie : nom='{nom}', prix={prix}€, marque_moteur={marque_moteur}, "
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
    logger.info("Démarrage du robot de chargement Cyclable")
    logger.info("=" * 70)

    liens = recuperer_liens_produits()
    logger.info(f"{len(liens)} fiches produits trouvées au total.")

    stats = {
        "inseres_ou_maj": 0,
        "rejetes_validation": 0,
        "ignores_non_velo_elec": 0,
        "erreurs": 0,
    }
    details_rejets = []

    for lien in liens:
        try:
            velo = analyser_fiche_produit(lien)

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
