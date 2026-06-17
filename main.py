import os
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD (Lecture dynamique depuis l'environnement Render)
# -------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "Erreur : La variable d'environnement 'DATABASE_URL' est introuvable sur Render."
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Token de sécurité secret pour valider les requêtes de l'administration et du GPT
ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (SQLAlchemy - Aligné sur 15 critères)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "velos"  # Cible la table 'velos' (sans accent, au pluriel)
    identifiant = Column("id", String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    marque = Column(String, nullable=True)
    modele = Column(String, nullable=True)
    prix = Column(Integer, default=0)
    marque_moteur = Column(String, nullable=True)
    couple_moteur = Column(Integer, default=0)
    puissance_moteur = Column(Integer, default=250)
    energie_batterie = Column(Integer, default=0)
    autonomie = Column(Integer, default=0)
    categorie = Column(String, nullable=True)  # Ville, VTT, Trekking, Cargo
    poids = Column(Float, default=0.0)
    taille_min = Column(Integer, default=150)
    taille_max = Column(Integer, default=200)
    suspension = Column(Boolean, default=False)
    description_ia = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

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
# INITIALISATION FASTAPI & CONFIGURATION CORS
# -------------------------------------------------------------------------
app = FastAPI(title="VéloÉlec & Co - API Administrative")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------------
# ROUTES DE L'API PUBLIQUE
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

# Route technique pour charger individuellement un seul vélo dans l'admin
@app.get("/api/velos/{id_velo}")
def recuperer_un_velo(id_velo: str, db: Session = Depends(get_db)):
    velo = db.query(VeloDB).filter(VeloDB.identifiant == id_velo).first()
    if not velo:
        raise HTTPException(status_code=404, detail="Vélo introuvable")
    return velo

@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# ROUTE COMPATIBLE GPT PERSONNALISÉ
# -------------------------------------------------------------------------
@app.get("/api/ia/catalogue")
def catalogue_pour_ia(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    return {
        "site": "VéloÉlec & Co",
        "version": "2.0",
        "nombre_velos": len(velos),
        "velos": [
            {
                "identifiant": v.identifiant,
                "nom": v.nom,
                "marque": v.marque or "",
                "modele": v.modele or "",
                "prix": v.prix,
                "marque_moteur": v.marque_moteur or "",
                "couple_moteur": v.couple_moteur,
                "puissance_moteur": v.puissance_moteur,
                "energie_batterie": v.energie_batterie,
                "autonomie": v.autonomie,
                "categorie": v.categorie or "",
                "poids": v.poids,
                "taille_min": v.taille_min,
                "taille_max": v.taille_max,
                "suspension": v.suspension,
                "description": v.description_ia or "",
                "image_url": v.image_url or ""
            }
            for v in velos
        ]
    }

# -------------------------------------------------------------------------
# TRAITEMENTS ADMIN : ENREGISTREMENTS ET MODIFICATIONS SÉCURISÉES
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo")
def ajouter_nouveau_velo(
    id: str = Form(...), nom: str = Form(...), marque: str = Form(None), modele: str = Form(None),
    prix: int = Form(0), marque_moteur: str = Form(None), couple_moteur: int = Form(0),
    puissance_moteur: int = Form(250), energie_batterie: int = Form(0), autonomie: int = Form(0),
    categorie: str = Form(None), poids: float = Form(0.0), taille_min: int = Form(150),
    taille_max: int = Form(200), suspension: bool = Form(False), description_ia: str = Form(None),
    image_url: str = Form(None), robot_token_form: str = Form(...), db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token secret incorrect.")
    
    velo_existant = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    if velo_existant:
        raise HTTPException(status_code=400, detail="L'identifiant existe déjà.")
    
    nouveau_velo = VeloDB(
        identifiant=id, nom=nom, marque=marque, modele=modele, prix=prix,
        marque_moteur=marque_moteur, couple_moteur=couple_moteur, puissance_moteur=puissance_moteur,
        energie_batterie=energie_batterie, autonomie=autonomie, categorie=categorie,
        poids=poids, taille_min=taille_min, taille_max=taille_max, suspension=suspension,
        description_ia=description_ia, image_url=image_url
    )
    db.add(nouveau_velo)
    db.commit()
    return {"status": "created", "message": f"Le vélo expert '{nom}' a été ajouté avec succès !"}

@app.post("/api/modifier-velo")
def modifier_velo_existant(
    id: str = Form(...), nom: str = Form(...), marque: str = Form(None), modele: str = Form(None),
    prix: int = Form(0), marque_moteur: str = Form(None), couple_moteur: int = Form(0),
    puissance_moteur: int = Form(250), energie_batterie: int = Form(0), autonomie: int = Form(0),
    categorie: str = Form(None), poids: float = Form(0.0), taille_min: int = Form(150),
    taille_max: int = Form(200), suspension: bool = Form(False), description_ia: str = Form(None),
    image_url: str = Form(None), robot_token_form: str = Form(...), db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token secret incorrect.")
    
    velo = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    if not velo:
        raise HTTPException(status_code=404, detail="Vélo introuvable dans Supabase.")
    
    # Mise à jour de l'ensemble des critères
    velo.nom = nom
    velo.marque = marque
    velo.modele = modele
    velo.prix = prix
    velo.marque_moteur = marque_moteur
    velo.couple_moteur = couple_moteur
    velo.puissance_moteur = puissance_moteur
    velo.energie_batterie = energie_batterie
    velo.autonomie = autonomie
    velo.categorie = categorie
    velo.poids = poids
    velo.taille_min = taille_min
    velo.taille_max = taille_max
    velo.suspension = suspension
    velo.description_ia = description_ia
    velo.image_url = image_url
    
    db.commit()
    return {"status": "success", "message": f"Le vélo '{nom}' a été mis à jour dans Supabase !"}

# -------------------------------------------------------------------------
# INTERFACES VISUELLES
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return "<h1>⚡ Serveur FastAPI actif (index.html manquant)</h1>"

@app.get("/admin.html")
def page_administration():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    raise HTTPException(status_code=404, detail="Le fichier admin.html est introuvable.")

@app.get("/hero-bike.jpg")
def distribuer_image_hero():
    if os.path.exists("hero-bike.jpg"):
        return FileResponse("hero-bike.jpg")
    raise HTTPException(status_code=404, detail="Image manquante.")

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return "User-agent: *\nAllow: /\nUser-agent: GPTBot\nAllow: /\n"