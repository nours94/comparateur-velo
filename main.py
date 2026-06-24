import os
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Erreur : La variable 'DATABASE_URL' est introuvable sur Render.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ROBOT_TOKEN = os.getenv("ROBOT_TOKEN")

if not ROBOT_TOKEN:
    raise RuntimeError("Erreur : la variable ROBOT_TOKEN est introuvable sur Render.")


# -------------------------------------------------------------------------
# MODÈLES SQLALCHEMY
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "velos"

    # Dans Supabase, la colonne s'appelle "id"
    # Dans Python, on l'utilise sous le nom "identifiant"
    identifiant = Column("id", String, primary_key=True, index=True)

    nom = Column(String, nullable=False)
    prix = Column(Integer, default=0)
    moteur = Column(String, nullable=True)
    batterie = Column(String, nullable=True)
    description_ia = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    marque = Column(String, nullable=True)
    modele = Column(String, nullable=True)

    # Champs ajoutés (alignés sur le schéma réel Supabase)
    marque_moteur = Column(String, nullable=True)
    couple_moteur = Column(Integer, nullable=True)      # Nm
    energie_moteur = Column(Integer, nullable=True)     # Watts
    autonomie = Column(Integer, nullable=True)           # km
    categorie = Column(String, nullable=True)
    poids = Column(Float, nullable=True)                 # kg
    taille_min = Column(Integer, nullable=True)           # cm
    taille_max = Column(Integer, nullable=True)           # cm


class ReparateurDB(Base):
    __tablename__ = "reparateurs"

    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    ville = Column(String, nullable=False)
    adresse = Column(String, nullable=False)
    telephone = Column(String, nullable=True)
    note = Column(Float, default=4.0)
    tarif_horaire = Column(Integer, default=50)
    specialites = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)


# -------------------------------------------------------------------------
# INITIALISATION FASTAPI
# -------------------------------------------------------------------------
app = FastAPI(title="VéloÉlec & Co - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------------
# SESSION BDD
# -------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------------
# OUTILS DE SÉRIALISATION
# -------------------------------------------------------------------------
def velo_to_dict(v: VeloDB):
    return {
        "identifiant": v.identifiant,
        "nom": v.nom,
        "marque": v.marque or "",
        "modele": v.modele or "",
        "prix": v.prix or 0,
        "moteur": v.moteur or "",
        "batterie": v.batterie or "",
        "description_ia": v.description_ia or "",
        "description": v.description_ia or "",
        "image_url": v.image_url or "",
        "marque_moteur": v.marque_moteur or "",
        "couple_moteur": v.couple_moteur,
        "energie_moteur": v.energie_moteur,
        "autonomie": v.autonomie,
        "categorie": v.categorie or "",
        "poids": v.poids,
        "taille_min": v.taille_min,
        "taille_max": v.taille_max,
    }


def reparateur_to_dict(r: ReparateurDB):
    return {
        "id": r.id,
        "nom": r.nom,
        "ville": r.ville,
        "adresse": r.adresse,
        "telephone": r.telephone or "",
        "note": r.note or 0,
        "tarif_horaire": r.tarif_horaire or 0,
        "specialites": r.specialites or "",
    }


def _vers_int(valeur):
    """Convertit une chaîne (potentiellement vide) en int, ou None."""
    if valeur is None or str(valeur).strip() == "":
        return None
    try:
        return int(float(valeur))
    except (ValueError, TypeError):
        return None


def _vers_float(valeur):
    """Convertit une chaîne (potentiellement vide) en float, ou None."""
    if valeur is None or str(valeur).strip() == "":
        return None
    try:
        return float(valeur)
    except (ValueError, TypeError):
        return None


# -------------------------------------------------------------------------
# ROUTES TECHNIQUES
# -------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "VéloÉlec & Co API"}


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n"
    )


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    if os.path.exists("llms.txt"):
        with open("llms.txt", "r", encoding="utf-8") as f:
            return PlainTextResponse(content=f.read())

    raise HTTPException(status_code=404, detail="llms.txt introuvable.")


@app.get("/sitemap.xml")
def sitemap_xml():
    if os.path.exists("sitemap.xml"):
        return FileResponse("sitemap.xml", media_type="application/xml")

    raise HTTPException(status_code=404, detail="sitemap.xml introuvable.")


# -------------------------------------------------------------------------
# ROUTES API PUBLIQUES
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    return [velo_to_dict(v) for v in velos]


@app.get("/api/velos/{id_velo}")
def recuperer_un_velo(id_velo: str, db: Session = Depends(get_db)):
    velo = db.query(VeloDB).filter(VeloDB.identifiant == id_velo).first()

    if not velo:
        raise HTTPException(status_code=404, detail="Vélo introuvable.")

    return velo_to_dict(velo)


@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    reparateurs = db.query(ReparateurDB).all()
    return [reparateur_to_dict(r) for r in reparateurs]


# -------------------------------------------------------------------------
# ROUTE IA POUR GPT PERSONNALISÉ
# -------------------------------------------------------------------------
@app.get("/api/ia/catalogue")
def catalogue_pour_ia(
    budget_max: int | None = None,
    categorie: str | None = None,
    taille_cm: int | None = None,
    recherche: str | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    """
    Catalogue allégé pour le GPT personnalisé.

    Objectif : ne pas renvoyer les 500 vélos d'un coup,
    mais permettre au GPT de filtrer intelligemment par budget,
    catégorie, taille et mots-clés, tout en conservant les photos.
    """

    # Sécurité : on évite qu'un appel GPT ramène trop de vélos
    if limit is None or limit <= 0:
        limit = 30
    limit = min(limit, 60)

    query = db.query(VeloDB)

    if budget_max is not None:
        query = query.filter(VeloDB.prix <= budget_max)

    # Important : les cargos peuvent être indiqués dans la catégorie,
    # mais aussi seulement dans le nom, le modèle ou la description.
    if categorie:
        mot = f"%{categorie}%"
        query = query.filter(
            (VeloDB.categorie.ilike(mot))
            | (VeloDB.nom.ilike(mot))
            | (VeloDB.modele.ilike(mot))
            | (VeloDB.description_ia.ilike(mot))
        )

    # Recherche libre complémentaire : ville, cargo, longtail, Bosch, enfant, etc.
    if recherche:
        mot = f"%{recherche}%"
        query = query.filter(
            (VeloDB.nom.ilike(mot))
            | (VeloDB.marque.ilike(mot))
            | (VeloDB.modele.ilike(mot))
            | (VeloDB.moteur.ilike(mot))
            | (VeloDB.batterie.ilike(mot))
            | (VeloDB.categorie.ilike(mot))
            | (VeloDB.description_ia.ilike(mot))
        )

    if taille_cm is not None:
        query = query.filter(
            (VeloDB.taille_min == None) | (VeloDB.taille_min <= taille_cm),
            (VeloDB.taille_max == None) | (VeloDB.taille_max >= taille_cm),
        )

    # On privilégie les vélos avec une photo, puis les prix croissants.
    velos = (
        query
        .order_by(
            VeloDB.image_url.desc(),
            VeloDB.prix.asc()
        )
        .limit(limit)
        .all()
    )

    return {
        "site": "VéloÉlec & Co",
        "version": "Progressive 1.4",
        "nombre_velos": len(velos),
        "conseil_affichage": "Pour afficher les photos dans ChatGPT, utiliser le champ photo_markdown.",
        "velos": [
            {
                "id": v.identifiant,
                "nom": v.nom,
                "marque": v.marque or "",
                "modele": v.modele or "",
                "prix": v.prix or 0,
                "categorie": v.categorie or "",
                "moteur": v.moteur or "",
                "batterie": v.batterie or "",
                "autonomie": v.autonomie,
                "couple_moteur": v.couple_moteur,
                "energie_moteur": v.energie_moteur,
                "poids": v.poids,
                "taille_min": v.taille_min,
                "taille_max": v.taille_max,
                "description_ia": v.description_ia or "",
                "image_url": v.image_url or "",
                "photo_markdown": f"![{v.nom}]({v.image_url})" if v.image_url else "",
            }
            for v in velos
        ],
    }

# -------------------------------------------------------------------------
# ROUTE QUESTIONNAIRE VELO
# -------------------------------------------------------------------------    
@app.get("/questionnaire.html", response_class=HTMLResponse)
def page_questionnaire():
    if os.path.exists("questionnaire.html"):
        with open("questionnaire.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    raise HTTPException(status_code=404, detail="questionnaire.html introuvable.")

# -------------------------------------------------------------------------
# ROUTE ADMIN : AJOUT D'UN VÉLO
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo")
def ajouter_nouveau_velo(
    id: str = Form(...),
    nom: str = Form(...),
    prix: int = Form(0),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    image_url: str = Form(None),
    marque: str = Form(None),
    modele: str = Form(None),
    marque_moteur: str = Form(None),
    couple_moteur: str = Form(None),
    energie_moteur: str = Form(None),
    autonomie: str = Form(None),
    categorie: str = Form(None),
    poids: str = Form(None),
    taille_min: str = Form(None),
    taille_max: str = Form(None),
    robot_token_form: str = Form(...),
    db: Session = Depends(get_db),
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Token incorrect.")

    velo_existant = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    if velo_existant:
        raise HTTPException(
            status_code=400,
            detail="Ce vélo existe déjà. Utilisez le mode modification.",
        )

    nouveau_velo = VeloDB(
        identifiant=id,
        nom=nom,
        prix=prix,
        moteur=moteur,
        batterie=batterie,
        description_ia=description_ia,
        image_url=image_url,
        marque=marque,
        modele=modele,
        marque_moteur=marque_moteur,
        couple_moteur=_vers_int(couple_moteur),
        energie_moteur=_vers_int(energie_moteur),
        autonomie=_vers_int(autonomie),
        categorie=categorie,
        poids=_vers_float(poids),
        taille_min=_vers_int(taille_min),
        taille_max=_vers_int(taille_max),
    )

    db.add(nouveau_velo)
    db.commit()

    return {"status": "created", "message": f"Le vélo '{nom}' a été ajouté !"}


# -------------------------------------------------------------------------
# ROUTE ADMIN : MODIFICATION D'UN VÉLO
# -------------------------------------------------------------------------
@app.post("/api/modifier-velo")
def modifier_velo_existant(
    id: str = Form(...),
    nom: str = Form(...),
    prix: int = Form(0),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    image_url: str = Form(None),
    marque: str = Form(None),
    modele: str = Form(None),
    marque_moteur: str = Form(None),
    couple_moteur: str = Form(None),
    energie_moteur: str = Form(None),
    autonomie: str = Form(None),
    categorie: str = Form(None),
    poids: str = Form(None),
    taille_min: str = Form(None),
    taille_max: str = Form(None),
    robot_token_form: str = Form(...),
    db: Session = Depends(get_db),
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Token incorrect.")

    velo = db.query(VeloDB).filter(VeloDB.identifiant == id).first()

    if not velo:
        raise HTTPException(status_code=404, detail="Vélo introuvable.")

    velo.nom = nom
    velo.prix = prix
    velo.moteur = moteur
    velo.batterie = batterie
    velo.description_ia = description_ia
    velo.image_url = image_url
    velo.marque = marque
    velo.modele = modele
    velo.marque_moteur = marque_moteur
    velo.couple_moteur = _vers_int(couple_moteur)
    velo.energie_moteur = _vers_int(energie_moteur)
    velo.autonomie = _vers_int(autonomie)
    velo.categorie = categorie
    velo.poids = _vers_float(poids)
    velo.taille_min = _vers_int(taille_min)
    velo.taille_max = _vers_int(taille_max)

    db.commit()

    return {"status": "success", "message": f"Le vélo '{nom}' a bien été mis à jour !"}


# -------------------------------------------------------------------------
# ROUTES FRONT-END
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return "<h1>⚡ Serveur FastAPI actif - fichier index.html manquant</h1>"


@app.get("/admin.html")
def page_administration():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")

    raise HTTPException(status_code=404, detail="admin.html introuvable.")


@app.get("/catalogue.html", response_class=HTMLResponse)
def page_catalogue():
    if os.path.exists("catalogue.html"):
        with open("catalogue.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    raise HTTPException(status_code=404, detail="catalogue.html introuvable.")


@app.get("/top-10-velos-ville-electriques.html", response_class=HTMLResponse)
def page_top10_ville():
    if os.path.exists("top-10-velos-ville-electriques.html"):
        with open("top-10-velos-ville-electriques.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    raise HTTPException(status_code=404, detail="top-10-velos-ville-electriques.html introuvable.")


@app.get("/hero-bike.jpg")
def distribuer_image_hero():
    if os.path.exists("hero-bike.jpg"):
        return FileResponse("hero-bike.jpg")

    raise HTTPException(status_code=404, detail="Image hero-bike.jpg introuvable.")
