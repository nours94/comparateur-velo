import os
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD (SQLite Local & Éphémère pour Render Gratuit)
# -------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./velos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Token de sécurité pour bloquer les robots inconnus
ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (SQLAlchemy)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "velos"
    id = Column(String, primary_key=True, index=True)
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

# Création des tables si elles n'existent pas
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------------
# INITIALISATION FASTAPI
# -------------------------------------------------------------------------
app = FastAPI(title="VéloÉlec & Co - Comparateur")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dépendance pour ouvrir/fermer la session de BDD à chaque requête
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------------
# CHARGEMENT AUTOMATIQUE DU CATALOGUE (Au démarrage du site)
# -------------------------------------------------------------------------
@app.on_event("startup")
def init_db():
    db = SessionLocal()
    try:
        # Si la base est neuve (ou réinitialisée par le reboot de Render)
        if db.query(VeloDB).count() == 0:
            # On vérifie si ton fichier de sauvegarde JSON existe
            if os.path.exists("velos.json"):
                with open("velos.json", "r", encoding="utf-8") as f:
                    liste_velos = json.load(f)
                    
                    # Boucle magique : importe automatiquement tes 3 ou 500 vélos !
                    for v in liste_velos:
                        db.add(VeloDB(
                            id=v.get("id"),
                            nom=v.get("nom"),
                            prix=v.get("prix", 0),
                            moteur=v.get("moteur"),
                            batterie=v.get("batterie"),
                            description_ia=v.get("description_ia"),
                            image_url=v.get("image_url")
                        ))
                db.commit()
                print(f"✅ {len(liste_velos)} vélos injectés avec succès depuis le fichier JSON !")
            else:
                print("ℹ️ Aucun fichier velos.json détecté. Base initialisée vide.")
            
        # Initialisation par défaut d'un réparateur si la table est vide
        if db.query(ReparateurDB).count() == 0:
            db.add(ReparateurDB(
                id="repar-elec-paris", 
                nom="Atelier Cyclo Élec Paris", 
                ville="Paris",
                adresse="15 Rue de Rivoli, 75001 Paris", 
                telephone="01 42 33 44 55", 
                note=4.8, 
                tarif_horaire=65,
                specialites="Moteurs Bosch, Shimano Steps, Diagnostics batteries"
            ))
            db.commit()
            print("✅ Réparateur par défaut ajouté.")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la BDD : {e}")
    finally:
        db.close()

# -------------------------------------------------------------------------
# ROUTES API : ACCÈS AUX DONNÉES (FRONTEND)
# -------------------------------------------------------------------------
@app.get("/api/velos")
def récupérer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

@app.get("/api/reparateurs")
def récupérer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# ROUTE API : ENREGISTREMENT ET MISE À JOUR (POUR TES ROBOTS)
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo")
def ajouter_ou_mettre_a_jour_velo(
    id: str = Form(...),
    nom: str = Form(...),
    prix: int = Form(0),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    image_url: str = Form(None),
    robot_token_form: str = Form(...),
    db: Session = Depends(get_db)
):
    # Vérification de la clé de sécurité du robot
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token de robot invalide.")
    
    # Recherche si le vélo existe déjà en BDD
    velo_existant = db.query(VeloDB).filter(VeloDB.id == id).first()
    
    if velo_existant:
        # MISE À JOUR : On met à jour uniquement les champs envoyés
        velo_existant.nom = nom
        if prix > 0: velo_existant.prix = prix
        if moteur: velo_existant.moteur = moteur
        if batterie: velo_existant.batterie = batterie
        if description_ia: velo_existant.description_ia = description_ia
        if image_url: velo_existant.image_url = image_url
        
        db.commit()
        return {"status": "success", "message": f"Fiche mise à jour pour : {nom}"}
    
    else:
        # CRÉATION : Le vélo n'existe pas, on l'ajoute
        nouveau_velo = VeloDB(
            id=id, nom=nom, prix=prix, moteur=moteur, 
            batterie=batterie, description_ia=description_ia, image_url=image_url
        )
        db.add(nouveau_velo)
        db.commit()
        return {"status": "created", "message": f"Nouveau vélo ajouté avec succès : {nom}"}

# -------------------------------------------------------------------------
# SERVIR LE FRONTEND (À laisser tout en bas)
# -------------------------------------------------------------------------
# Permet de lier ton dossier frontend si tu as des fichiers statiques (CSS, JS, Images)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("static/index.html"):
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return """
    <html>
        <head><title>VéloÉlec & Co</title></head>
        <body style="font-family:sans-serif; text-align:center; padding-top:50px;">
            <h1>⚡ Bienvenue sur VéloÉlec & Co API</h1>
            <p>Le serveur FastAPI fonctionne correctement. Le fichier index.html est introuvable dans /static.</p>
        </body>
    </html>
    """