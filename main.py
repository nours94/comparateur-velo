import os
import json
import urllib.parse
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD (Connexion Supabase PostgreSQL Forcée et Sécurisée)
# -------------------------------------------------------------------------
# Définition sécurisée du mot de passe avec caractères spéciaux
mot_de_passe = "$$Batman1966**"
mdp_encode = urllib.parse.quote_plus(mot_de_passe)

# Utilisation directe du pooler Supabase (port 6543) requis pour Render
DATABASE_URL = f"postgresql://postgres.ekysiizbxuvhcvugdrtp:{mdp_encode}@aws-1-eu-north-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Token de sécurité secret pour valider les envois du formulaire admin
ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (SQLAlchemy)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "vélo"  # Aligné exactement sur le nom de ta table Supabase
    identifiant = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prix = Column(Integer, default=0)
    moteur = Column(String, nullable=True)
    batterie = Column(String, nullable=True)
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

# Création automatique des tables dans Supabase si manquantes
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------------
# INITIALISATION FASTAPI & CONFIGURATION CORS
# -------------------------------------------------------------------------
app = FastAPI(title="VéloÉlec & Co - Comparateur Supabase")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Injecteur de session BDD pour chaque requête
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialisation automatique du catalogue au démarrage si vide
@app.on_event("startup")
def init_db():
    db = SessionLocal()
    try:
        if db.query(VeloDB).count() == 0 and os.path.exists("velos.json"):
            with open("velos.json", "r", encoding="utf-8") as f:
                liste_velos = json.load(f)
                for v in liste_velos:
                    db.add(VeloDB(
                        identifiant=v.get("id"), nom=v.get("nom"), prix=v.get("prix", 0),
                        moteur=v.get("moteur"), batterie=v.get("batterie"),
                        description_ia=v.get("description_ia"), image_url=v.get("image_url")
                    ))
            db.commit()
            print("✅ Initialisation du catalogue vélos réussie.")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation : {e}")
    finally:
        db.close()

# -------------------------------------------------------------------------
# ROUTES D'AFFICHAGE PUBLIC (API)
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# ROUTE ADMINISTRATEUR : AJOUT D'UN VÉLO
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo")
def ajouter_nouveau_velo(
    id: str = Form(...), nom: str = Form(...), prix: int = Form(0),
    moteur: str = Form(None), batterie: str = Form(None),
    description_ia: str = Form(None), image_url: str = Form(None),
    robot_token_form: str = Form(...), db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token invalide.")
    
    velo_existant = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    if velo_existant:
        raise HTTPException(status_code=400, detail="Ce vélo existe déjà. Utilisez le mode modification.")
    
    nouveau_velo = VeloDB(
        identifiant=id, nom=nom, prix=prix, moteur=moteur, 
        batterie=batterie, description_ia=description_ia, image_url=image_url
    )
    db.add(nouveau_velo)
    db.commit()
    return {"status": "created", "message": f"Nouveau vélo '{nom}' ajouté avec succès dans Supabase !"}

# -------------------------------------------------------------------------
# ROUTE ADMINISTRATEUR : MODIFICATION D'UN VÉLO
# -------------------------------------------------------------------------
@app.post("/api/modifier-velo")
def modifier_velo_existant(
    id: str = Form(...), nom: str = Form(...), prix: int = Form(0),
    moteur: str = Form(None), batterie: str = Form(None),
    description_ia: str = Form(None), image_url: str = Form(None),
    robot_token_form: str = Form(...), db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token invalide.")
    
    velo = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    if not velo:
        raise HTTPException(status_code=404, detail="Désolé, ce vélo n'existe pas dans Supabase.")
    
    velo.nom = nom
    velo.prix = prix
    velo.moteur = moteur
    velo.batterie = batterie
    velo.description_ia = description_ia
    velo.image_url = image_url
    
    db.commit()
    return {"status": "success", "message": f"Le vélo '{nom}' a été mis à jour avec succès dans Supabase !"}

# -------------------------------------------------------------------------
# ROUTES D'AFFICHAGE DES PAGES WEB (HTML)
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

# -------------------------------------------------------------------------
# OPTIMISATION RECHERCHE IA (GEO) : FICHIER ROBOTS.TXT
# -------------------------------------------------------------------------
@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    contenu = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "# Autoriser explicitement les moteurs d'apprentissage et de recherche IA\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n"
    )
    return contenu