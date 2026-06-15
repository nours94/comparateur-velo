import os
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD (Connexion Supabase PostgreSQL avec mot de passe encodé)
# -------------------------------------------------------------------------
# 1. On tente d'abord de récupérer la variable configurée sur Render
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Si Render ne la fournit pas (test en local), on reconstruit l'URL proprement.
# Note : Les symboles $ et * de ton mot de passe sont remplacés par %24 et %2A pour éviter le plantage
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres.ekysiizbxuvhcvugdrtp:%24%24Batman1966%2A%2A@aws-1-eu-north-1.pooler.supabase.com:6543/postgres?pgbouncer=true"

# 3. Sécurité obligatoire pour SQLAlchemy : convertit "postgres://" en "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuration du moteur de base de données
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Token de sécurité secret pour valider les envois du formulaire admin
ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (SQLAlchemy aligné sur Supabase)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "vélo"  # Cible le nom exact de ta table Supabase (avec l'accent)
    
    # Alignement complet sur les colonnes de ton tableau de bord Supabase
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

# Création automatique des tables si elles n'existent pas encore
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

# Injecteur de session BDD pour chaque requête de route
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------------
# INITIALISATION DU CATALOGUE (Au démarrage)
# -------------------------------------------------------------------------
@app.on_event("startup")
def init_db():
    db = SessionLocal()
    try:
        # Initialisation si la table Supabase est totalement vide
        if db.query(VeloDB).count() == 0:
            if os.path.exists("velos.json"):
                with open("velos.json", "r", encoding="utf-8") as f:
                    liste_velos = json.load(f)
                    for v in liste_velos:
                        db.add(VeloDB(
                            identifiant=v.get("id"),
                            nom=v.get("nom"),
                            prix=v.get("prix", 0),
                            moteur=v.get("moteur"),
                            batterie=v.get("batterie"),
                            description_ia=v.get("description_ia"),
                            image_url=v.get("image_url")
                        ))
                db.commit()
                print(f"✅ {len(liste_velos)} vélos injectés dans Supabase.")
            
        if db.query(ReparateurDB).count() == 0:
            db.add(ReparateurDB(
                id="repar-elec-paris", 
                nom="Atelier Cyclo Élec Paris", 
                ville="Paris",
                adresse="15 Rue de Rivoli, 75001 Paris", 
                telephone="01 42 33 44 55", 
                note=4.8, 
                tarif_horaire=65,
                specialites="Moteurs Bosch, Shimano Steps"
            ))
            db.commit()
            print("✅ Réparateur par défaut configuré.")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation : {e}")
    finally:
        db.close()

# -------------------------------------------------------------------------
# ROUTES D'AFFICHAGE PUBLIC
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# ROUTE 1 : AJOUT D'UN NOUVEAU VÉLO
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo")
def ajouter_nouveau_velo(
    id: str = Form(...),  # Reçoit l'ID depuis le champ 'id' du formulaire admin.html
    nom: str = Form(...),
    prix: int = Form(0),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    image_url: str = Form(None),
    robot_token_form: str = Form(...),
    db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token invalide.")
    
    # Vérifie si le vélo existe déjà sous cet identifiant dans Supabase
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
# ROUTE 2 : MODIFICATION D'UN VÉLO EXISTANT
# -------------------------------------------------------------------------
@app.post("/api/modifier-velo")
def modifier_velo_existant(
    id: str = Form(...),  # Reçoit l'ID depuis le champ 'id' du formulaire admin.html
    nom: str = Form(...),
    prix: int = Form(0),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    image_url: str = Form(None),
    robot_token_form: str = Form(...),
    db: Session = Depends(get_db)
):
    if robot_token_form != ROBOT_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé : Token invalide.")
    
    # Recherche filtrée par la colonne 'identifiant' de Supabase
    velo = db.query(VeloDB).filter(VeloDB.identifiant == id).first()
    
    if not velo:
        raise HTTPException(status_code=404, detail="Désolé, ce vélo n'existe pas dans Supabase.")
    
    # Mise à jour des valeurs
    velo.nom = nom
    velo.prix = prix
    velo.moteur = moteur
    velo.batterie = batterie
    velo.description_ia = description_ia
    velo.image_url = image_url
    
    db.commit()
    return {"status": "success", "message": f"Le vélo '{nom}' a été mis à jour avec succès dans Supabase !"}

# -------------------------------------------------------------------------
# AFFICHAGE DES PAGES HTML
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    elif os.path.exists("admin.html"):
        with open("admin.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
            
    return "<h1>⚡ Serveur FastAPI actif (index.html manquant)</h1>"

@app.get("/admin.html")
def page_administration():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    raise HTTPException(status_code=404, detail="Le fichier admin.html est introuvable.")