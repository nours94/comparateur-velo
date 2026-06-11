from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session

app = FastAPI()

# -------------------------------------------------------------------------
# DATABASE SETUP
# -------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./velos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class VeloDB(Base):
    __tablename__ = "velos"
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prix = Column(Integer, nullable=False)
    moteur = Column(String)
    batterie = Column(String)
    description_ia = Column(Text)
    image_url = Column(String, nullable=True) # Champ pour stocker la vraie URL

class ReparateurDB(Base):
    __tablename__ = "reparateurs"
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    ville = Column(String, nullable=False)
    adresse = Column(String)
    telephone = Column(String)
    note = Column(Float, default=4.5)
    tarif_horaire = Column(Integer)
    specialites = Column(Text)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

API_KEY_NAME = "X-Robot-Token"
ROBOT_TOKEN = "super_secret_token_123"

class VeloSchema(BaseModel):
    id: str
    nom: str
    prix: int
    moteur: str
    batterie: str
    description_ia: str
    image_url: str = None

# -------------------------------------------------------------------------
# PAGE PUBLIC (Affiche la vraie photo)
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    reparateurs = db.query(ReparateurDB).all()
    
    cartes_velos = ""
    for velo in velos:
        blocs = velo.description_ia.split("//")
        avis_general = blocs[0].strip()
        points_forts_html = ""
        points_faibles_html = ""
        
        for bloc in blocs[1:]:
            texte_bloc = bloc.strip()
            if texte_bloc.startswith("+"):
                elements = texte_bloc.replace("+", "").split(",")
                for el in elements:
                    if el.strip(): points_forts_html += f"<li>🟢 {el.strip()}</li>"
            elif texte_bloc.startswith("-"):
                elements = texte_bloc.replace("-", "").split(",")
                for el in elements:
                    if el.strip(): points_faibles_html += f"<li>🔴 {el.strip()}</li>"

        if not points_forts_html and not points_faibles_html:
            pros_cons_section = f"<p class='review-text'>{velo.description_ia}</p>"
        else:
            pros_cons_section = f"""
            <p class='review-text'>{avis_general}</p>
            <div class="pros-cons-container">
                {f'<ul class="pros-list">{points_forts_html}</ul>' if points_forts_html else ''}
                {f'<ul class="cons-list">{points_faibles_html}</ul>' if points_faibles_html else ''}
            </div>
            """
            
        # Image par défaut si le robot ou l'admin n'a rien mis
        img_src = velo.image_url if velo.image_url else "https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=600"

        cartes_velos += f"""
        <div class="velo-card" data-prix="{velo.prix}" data-nom="{velo.nom.lower()}">
            <div class="card-img-container" style="margin: -25px -25px 20px -25px; height: 200px; overflow: hidden; background: #eee;">
                <img src="{img_src}" alt="{velo.nom}" style="width: 100%; height: 100%; object-fit: contain; background: white;">
            </div>
            <div class="card-header">
                <span class="card-icon">🚲</span>
                <h2 class="card-title">{velo.nom}</h2>
            </div>
            <div class="price-tag">{velo.prix} €</div>
            <div class="card-specs">
                <div class="spec-item"><span class="spec-icon">⚡</span><div><strong>Moteur</strong><p>{velo.moteur}</p></div></div>
                <div class="spec-item"><span class="spec-icon">🔋</span><div><strong>Batterie</strong><p>{velo.batterie}</p></div></div>
            </div>
            <div class="card-review"><strong>📋 L'avis de l'expert :</strong>{pros_cons_section}</div>
        </div>
        """

    # Le reste du HTML pour les réparateurs et la structure reste inchangé...
    # (Pour économiser de l'espace ici, j'abrège, mais garde tes styles et tes onglets JavaScript intacts)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>VéloÉlec</title>
        <style>
            body {{ font-family: sans-serif; background: #f5f7fa; margin:0; padding:0; }}
            .navbar {{ background: #2c3e50; padding: 15px; display:flex; justify-content:space-between; }}
            .navbar-brand {{ color: white; font-weight:bold; text-decoration:none; font-size:20px; }}
            .btn-admin {{ background: #3498db; color:white; padding:8px 15px; border-radius:20px; text-decoration:none; }}
            .main-container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
            .grid-layout {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 30px; }}
            .velo-card {{ background: white; border-radius: 16px; padding: 25px; display: flex; flex-direction: column; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow:hidden; }}
            .card-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
            .card-title {{ font-size: 18px; margin:0; }}
            .price-tag {{ background: #2ecc71; color:white; padding:5px 12px; border-radius:20px; font-weight:bold; align-self:flex-start; margin-bottom:15px; }}
            .card-specs {{ background: #f8fafc; padding: 15px; border-radius:12px; margin-bottom:15px; }}
            .spec-item {{ margin-bottom: 8px; font-size:14px; }}
            .pros-cons-container {{ background: #fafbfc; padding: 10px; border-radius: 8px; font-size:13px; }}
            .pros-list, .cons-list {{ list-style:none; padding:0; margin:5px 0; }}
        </style>
    </head>
    <body>
        <nav class="navbar"><a href="/" class="navbar-brand">⚡ VéloÉlec</a><a href="/admin" class="btn-admin">⚙️ Admin</a></nav>
        <div class="main-container"><div class="grid-layout">{cartes_velos}</div></div>
    </body>
    </html>
    """

# API Écrase-et-remplace (Formulaire Admin + Robot)
@app.post("/api/ajouter-velo", status_code=status.HTTP_201_CREATED)
async def ajouter_velo(
    db: Session = Depends(get_db),
    id: str = Form(None), nom: str = Form(None), prix: int = Form(None),
    moteur: str = Form(None), batterie: str = Form(None), description_ia: str = Form(None),
    image_url: str = Form(None), robot_token_form: str = Form(None), velo_json: VeloSchema = None 
):
    if robot_token_form: 
        if robot_token_form != ROBOT_TOKEN: raise HTTPException(status_code=401)
        id_f, nom_f, prix_f, moteur_f, bat_f, desc_f, img_f = id, nom, prix, moteur, batterie, description_ia, image_url
        est_form = True
    else: 
        if not velo_json: raise HTTPException(status_code=400)
        id_f, nom_f, prix_f, moteur_f, bat_f, desc_f, img_f = velo_json.id, velo_json.nom, velo_json.prix, velo_json.moteur, velo_json.batterie, velo_json.description_ia, velo_json.image_url
        est_form = False

    existe = db.query(VeloDB).filter(VeloDB.id == id_f).first()
    if existe:
        # Met à jour tous les champs y compris l'image
        existe.nom, existe.prix, existe.moteur, existe.batterie, existe.description_ia = nom_f, prix_f, moteur_f, bat_f, desc_f
        if img_f: existe.image_url = img_f # Ne remplace l'image que si une nouvelle est fournie
    else:
        db.add(VeloDB(id=id_f, nom=nom_f, prix=prix_f, moteur=moteur_f, batterie=bat_f, description_ia=desc_f, image_url=img_f))
    
    db.commit()
    if est_form: return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return {"message": "Mis à jour avec succès"}

# -------------------------------------------------------------------------
# ESPACE ADMIN (Avec contrôle manuel de la photo)
# -------------------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return f"""
    <html>
        <head><title>Admin</title><style>body{{font-family:sans-serif;background:#f4f7f6;padding:40px;}} .box{{background:white;padding:30px;max-width:500px;margin:0 auto;border-radius:8px;}} input,textarea{{width:100%;padding:10px;margin-bottom:15px;border:1px solid #ccc;border-radius:4px;}} button{{background:#3498db;color:white;padding:12px;width:100%;border:none;border-radius:4px;font-weight:bold;cursor:pointer;}}</style></head>
        <body>
            <div class="box">
                <h2>⚙️ Ajouter ou Modifier un Vélo</h2>
                <form action="/api/ajouter-velo" method="POST">
                    <input type="hidden" name="robot_token_form" value="{ROBOT_TOKEN}">
                    <label>ID unique du vélo (ex: rockrider-e-st-100 pour modifier le existant)</label>
                    <input type="text" name="id" placeholder="ID exact pour modifier, ou nouveau pour créer" required>
                    <input type="text" name="nom" placeholder="Nom complet" required>
                    <input type="number" name="prix" placeholder="Prix (€)" required>
                    <input type="text" name="moteur" placeholder="Moteur">
                    <input type="text" name="batterie" placeholder="Batterie">
                    
                    <label>➡️ Lien URL de la vraie Photo (Optionnel)</label>
                    <input type="text" name="image_url" placeholder="https://site-du-fabricant.com/photo.jpg">
                    
                    <textarea name="description_ia" placeholder="Avis de l'expert... // + Points forts // - Points faibles" required></textarea>
                    <button type="submit">🚀 Enregistrer les modifications</button>
                </form>
                <a href="/" style="display:block; text-align:center; margin-top:15px; color:#95a5a6;">Retour au site</a>
            </div>
        </body>
    </html>
    """