import os
import json
from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------------
# CONFIGURATION BDD
# -------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "Erreur : La variable d'environnement 'DATABASE_URL' est introuvable sur Render."
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ROBOT_TOKEN = os.getenv("ROBOT_TOKEN", "super_secret_token_123")

# -------------------------------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES (Ajusté sur ta table Supabase réelle)
# -------------------------------------------------------------------------
class VeloDB(Base):
    __tablename__ = "velos"  # REPARÉ : correspond exactement à ta capture Supabase
    identifiant = Column("id", String, primary_key=True, index=True) # Aligné sur la colonne 'id'
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

Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------------
# INITIALISATION FASTAPI & CORS
# -------------------------------------------------------------------------
app = FastAPI(title="VéloÉlec & Co - Comparateur Supabase & GPT")

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
# ROUTES DE L'API
# -------------------------------------------------------------------------
@app.get("/api/velos")
def recuperer_tous_les_velos(db: Session = Depends(get_db)):
    return db.query(VeloDB).all()

@app.get("/api/reparateurs")
def recuperer_tous_les_reparateurs(db: Session = Depends(get_db)):
    return db.query(ReparateurDB).all()

# -------------------------------------------------------------------------
# RESTAURÉ : LA ROUTE SPÉCIALE POUR TON GPT PERSONNALISÉ
# -------------------------------------------------------------------------
@app.get("/api/ia/catalogue")
def catalogue_pour_ia(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    return {
        "site": "VéloÉlec & Co",
        "version": "1.0",
        "objectif": "Comparateur indépendant de vélos électriques",
        "nombre_velos": len(velos),
        "velos": [
            {
                "identifiant": v.identifiant,
                "nom": v.nom,
                "prix": v.prix,
                "moteur": v.moteur or "",
                "batterie": v.batterie or "",
                "description": v.description_ia or "",
                "image_url": v.image_url or ""
            }
            for v in velos
        ]
    }

# -------------------------------------------------------------------------
# ROUTES WRITING (AJOUT / MODIFICATION)
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
        raise HTTPException(status_code=400, detail="Ce vélo existe déjà.")
    
    nouveau_velo = VeloDB(
        identifiant=id, nom=nom, prix=prix, moteur=moteur, 
        batterie=batterie, description_ia=description_ia, image_url=image_url
    )
    db.add(nouveau_velo)
    db.commit()
    return {"status": "created", "message": f"Vélo '{nom}' ajouté !"}

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
        raise HTTPException(status_code=404, detail="Vélo introuvable.")
    
    velo.nom = nom
    velo.prix = prix
    velo.moteur = moteur
    velo.batterie = batterie
    velo.description_ia = description_ia
    velo.image_url = image_url
    
    db.commit()
    return {"status": "success", "message": f"Vélo '{nom}' mis à jour !"}

# -------------------------------------------------------------------------
# INTERFACES FRONT-END & ROBOTS
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return "<h1>⚡ Serveur FastAPI actif</h1>"

@app.get("/admin.html")
def page_administration():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    raise HTTPException(status_code=404, detail="Fichier introuvable.")

@app.get("/hero-bike.jpg")
def distribuer_image_hero():
    if os.path.exists("hero-bike.jpg"):
        return FileResponse("hero-bike.jpg")
    raise HTTPException(status_code=404, detail="Image introuvable.")

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return "User-agent: *\nAllow: /\nUser-agent: GPTBot\nAllow: /"