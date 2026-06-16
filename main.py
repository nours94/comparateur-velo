import os
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD (Lecture dynamique depuis l'environnement Render)
# -------------------------------------------------------------------------
# Récupération sécurisée de la chaîne de connexion Supabase configurée sur Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Sécurité : Si tu as oublié de la configurer sur Render, l'application t'avertira proprement
if not DATABASE_URL:
    raise RuntimeError(
        "Erreur : La variable d'environnement 'DATABASE_URL' est introuvable sur Render. "
        "Veuillez l'ajouter dans l'onglet 'Environment' de votre dashboard Render."
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Token de sécurité secret pour valider les envois du formulaire admin
ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (SQLAlchemy)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "vélo"  # Doit correspondre exactement au nom de ta table Supabase
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

# Création automatique des tables dans Supabase si elles n'existent pas
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

# Gestionnaire de sessions de base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Remplissage initial automatique du catalogue au démarrage de Render (si vide)
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
            print("✅ Initialisation réussie : vélos injectés dans Supabase.")
    except Exception as e:
        print(f"❌ Erreur lors du peuplement de la base : {e}")
    finally:
        db.close()

# -------------------------------------------------------------------------
# ROUTES DE L'API PUBLIQUE
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# ROUTE SPÉCIALE IA : CATALOGUE COMPLET POUR CHATGPT ET AUTRES IA
# -------------------------------------------------------------------------
@app.get("/api/ia/catalogue")
def catalogue_pour_ia(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    reparateurs = db.query(ReparateurDB).all()

    return {
        "site": "VéloÉlec & Co",
        "version": "1.0",
        "objectif": "Comparateur indépendant de vélos électriques",
        "description": "Catalogue structuré destiné aux assistants IA et moteurs de recherche intelligents.",
        "nombre_velos": len(velos),
        "nombre_reparateurs": len(reparateurs),
        "velos": velos,
        "reparateurs": reparateurs
    }

# -------------------------------------------------------------------------
# ROUTE ADMIN : AJOUT D'UN VÉLO
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
# ROUTE ADMIN : MODIFICATION D'UN VÉLO
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
# INTERFACES FRONT-END (HTML)
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return "<h1>⚡ Serveur FastAPI actif (Fichier index.html manquant)</h1>"

@app.get("/admin.html")
def page_administration():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    raise HTTPException(status_code=404, detail="Le fichier admin.html est introuvable.")

# 🛠️ AJOUT ROUTE TECHNIQUE : Autoriser et distribuer l'image de fond du Hero
@app.get("/hero-bike.jpg")
def distribuer_image_hero():
    if os.path.exists("hero-bike.jpg"):
        return FileResponse("hero-bike.jpg")
    raise HTTPException(status_code=404, detail="L'image hero-bike.jpg est introuvable à la racine.")

# -------------------------------------------------------------------------
# VISIBILITÉ MOTEURS IA (GEO) : CONFIGURATION ROBOTS.TXT
# -------------------------------------------------------------------------
@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    contenu = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "# Autoriser explicitement les moteurs d'indexation et de recherche IA\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n"
    )
    return contenu