from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session

app = FastAPI()

# -------------------------------------------------------------------------
# CONFIGURATION DE LA BASE DE DONNÉES (SQLite)
# -------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./velos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Table pour les Vélos (Avec le support de la colonne image_url)
class VeloDB(Base):
    __tablename__ = "velos"
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prix = Column(Integer, nullable=False)
    moteur = Column(String)
    batterie = Column(String)
    description_ia = Column(Text)
    image_url = Column(String, nullable=True)

# Table pour les Réparateurs
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

# Sécurité pour le robot
API_KEY_NAME = "X-Robot-Token"
ROBOT_TOKEN = "super_secret_token_123"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Schéma Pydantic pour le Robot
class VeloSchema(BaseModel):
    id: str
    nom: str
    prix: int
    moteur: str
    batterie: str
    description_ia: str
    image_url: str = None

@app.on_event("startup")
def init_db():
    db = SessionLocal()
    if db.query(VeloDB).count() == 0:
        db.add_all([
            VeloDB(
                id="rockrider-e-st-100", nom="Decathlon Rockrider E-ST 100", prix=999,
                moteur="Moteur roue arrière 42Nm", batterie="380 Wh",
                description_ia="Idéal pour débuter le VTT électrique à petit prix. // + Prix très accessible, cadre robuste, position confortable. // - Moteur arrière limité en forte pente, autonomie juste pour les longues sorties.",
                image_url="https://images.unsplash.com/photo-1532298229144-0ec0c57515c7?w=600"
            ),
            VeloDB(
                id="nakamura-e-crossover", nom="Intersport Nakamura E-Crossover", prix=1599,
                moteur="Moteur central Naka Hub One 60Nm", batterie="460 Wh",
                description_ia="Le meilleur rapport qualité/prix urbain actuel. // + Moteur central coupleux (60Nm), équipement complet, bonne autonomie. // - Esthétique un peu classique, poids important.",
                image_url="https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=600"
            )
        ])
        db.commit()
    if db.query(ReparateurDB).count() == 0:
        db.add_all([
            ReparateurDB(
                id="repar-elec-paris", nom="Atelier Cyclo Élec Paris", ville="Paris",
                adresse="15 Rue de Rivoli, 75001 Paris", telephone="01 42 33 44 55", note=4.8, tarif_horaire=65,
                specialites="Moteurs Bosch, Shimano Steps, Diagnostics batteries, Électricité VAE"
            )
        ])
        db.commit()
    db.close()

# -------------------------------------------------------------------------
# ROUTE PRINCIPALE PUBLIC
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    reparateurs = db.query(ReparateurDB).all()
    
    # 1. Génération des cartes de vélos
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
            
        # Image récupérée par le robot ou l'admin (avec secours)
        img_src = velo.image_url if velo.image_url else "https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=600"

        cartes_velos += f"""
        <div class="velo-card" data-prix="{velo.prix}" data-nom="{velo.nom.lower()}" data-moteur="{velo.moteur.lower() if velo.moteur else ''}">
            <div class="card-img-container">
                <img src="{img_src}" alt="{velo.nom}" loading="lazy">
            </div>
            <div class="card-header">
                <span class="card-icon">🚲</span>
                <h2 class="card-title">{velo.nom}</h2>
            </div>
            <div class="price-tag">{velo.prix} €</div>
            <div class="card-specs">
                <div class="spec-item"><span class="spec-icon">⚡</span><div><strong>Moteur</strong><p>{velo.moteur or 'Non spécifié'}</p></div></div>
                <div class="spec-item"><span class="spec-icon">🔋</span><div><strong>Batterie</strong><p>{velo.batterie or 'Non spécifié'}</p></div></div>
            </div>
            <div class="card-review"><strong>📋 L'avis de l'expert :</strong>{pros_cons_section}</div>
        </div>
        """

    # 2. Génération des cartes de réparateurs
    cartes_reparateurs = ""
    for rep in reparateurs:
        cartes_reparateurs += f"""
        <div class="reparateur-card" data-ville="{rep.ville.lower()}" data-nom="{rep.nom.lower()}" data-tarif="{rep.tarif_horaire or 0}">
            <div class="card-header">
                <span class="card-icon">🔧</span>
                <h2 class="card-title">{rep.nom}</h2>
            </div>
            <div class="price-tag status-blue">{rep.tarif_horaire if rep.tarif_horaire else '--'} €/h</div>
            <div class="rating-tag">⭐ {rep.note} / 5</div>
            <div class="card-specs" style="background: #fdf6ec;">
                <div class="spec-item"><span class="spec-icon">📍</span><div><strong>Localisation</strong><p>{rep.adresse} ({rep.ville})</p></div></div>
                <div class="spec-item"><span class="spec-icon">📞</span><div><strong>Contact</strong><p>{rep.telephone if rep.telephone else 'Non renseigné'}</p></div></div>
            </div>
            <div class="card-review" style="border-top: 1px dashed #e67e22;">
                <strong>🛠️ Spécialités :</strong>
                <p style="font-size: 14px; color: #555; margin: 5px 0 0 0; line-height: 1.4;">{rep.specialites or ''}</p>
            </div>
        </div>
        """
        
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VéloÉlec - Le Comparateur</title>
        <style>
            :root {{
                --primary: #3498db; --primary-dark: #2980b9; --dark: #2c3e50; --bg: #f5f7fa; --card-bg: #ffffff; --text: #34495e; --success: #2ecc71;
            }}
            body {{ font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 0; }}
            .navbar {{ background-color: var(--dark); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .navbar-brand {{ color: white; font-size: 22px; font-weight: bold; text-decoration: none; }}
            .btn-admin {{ background-color: var(--primary); color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; font-weight: bold; font-size: 14px; transition: all 0.3s; }}
            .btn-admin:hover {{ background-color: var(--primary-dark); transform: translateY(-2px); }}
            .main-container {{ max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
            
            .tabs-container {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 35px; }}
            .tab-btn {{ padding: 12px 28px; border: none; font-size: 16px; font-weight: bold; border-radius: 30px; cursor: pointer; transition: all 0.3s; background: #e2e8f0; color: var(--text); }}
            .tab-btn.active {{ background: var(--dark); color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
            
            .filter-bar {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 30px; display: flex; flex-wrap: wrap; gap: 20px; align-items: center; justify-content: space-between; border: 1px solid #e2e8f0; }}
            .filter-group {{ display: flex; align-items: center; gap: 10px; }}
            .filter-group label {{ font-weight: bold; font-size: 14px; color: var(--dark); }}
            .filter-bar input, .filter-bar select {{ padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; background-color: #f8fafc; }}
            
            .grid-layout {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 30px; margin-top: 20px; }}
            
            .velo-card, .reparateur-card {{ background: var(--card-bg); border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); padding: 25px; display: flex; flex-direction: column; transition: all 0.3s; border: 1px solid rgba(0,0,0,0.02); overflow: hidden; }}
            .velo-card:hover, .reparateur-card:hover {{ transform: translateY(-5px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }}
            
            .card-img-container {{ margin: -25px -25px 20px -25px; height: 200px; overflow: hidden; background-color: white; position: relative; border-bottom: 1px solid #edf2f7; }}
            .card-img-container img {{ width: 100%; height: 100%; object-fit: contain; transition: transform 0.5s; }}
            .velo-card:hover .card-img-container img {{ transform: scale(1.03); }}

            .card-header {{ display: flex; align-items: flex-start; gap: 12px; margin-bottom: 15px; }}
            .card-icon {{ font-size: 24px; background: #e8f4fd; padding: 8px; border-radius: 12px; }}
            .card-title {{ font-size: 20px; color: var(--dark); margin: 0; line-height: 1.3; }}
            .price-tag {{ align-self: flex-start; background-color: var(--success); color: white; padding: 6px 16px; font-weight: bold; font-size: 18px; border-radius: 30px; margin-bottom: 15px; }}
            .price-tag.status-blue {{ background-color: var(--primary); }}
            .rating-tag {{ font-size: 14px; font-weight: bold; color: #f1c40f; margin-bottom: 15px; margin-top: -10px; }}
            .card-specs {{ background: #f8fafc; border-radius: 12px; padding: 15px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 12px; }}
            .spec-item {{ display: flex; align-items: center; gap: 12px; }}
            .spec-icon {{ font-size: 18px; }}
            .spec-item strong {{ font-size: 12px; text-transform: uppercase; color: #95a5a6; display: block; }}
            .spec-item p {{ margin: 2px 0 0 0; font-size: 14px; color: var(--dark); font-weight: 500; }}
            .card-review {{ border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: auto; }}
            .card-review strong {{ font-size: 14px; color: var(--dark); display: block; margin-bottom: 6px; }}
            .review-text {{ margin: 0 0 15px 0; font-style: italic; font-size: 14px; color: #555; line-height: 1.5; }}
            .pros-cons-container {{ display: flex; flex-direction: column; gap: 10px; font-size: 13px; background: #fafbfc; padding: 12px; border-radius: 8px; }}
            .pros-list, .cons-list {{ margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 5px; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <a href="/" class="navbar-brand">⚡ VéloÉlec & Co</a>
            <a href="/admin" class="btn-admin">⚙️ Espace Admin</a>
        </nav>
        
        <div class="main-container">
            <div class="tabs-container">
                <button class="tab-btn active" id="btnVelos" onclick="switchTab('velos')">🚲 Comparer les Vélos</button>
                <button class="tab-btn" id="btnReparateurs" onclick="switchTab('reparateurs')">🔧 Trouver un Réparateur</button>
            </div>
            
            <div id="sectionVelos">
                <div class="filter-bar">
                    <div class="filter-group"><label>🔍 Rechercher</label><input type="text" id="searchVelo" placeholder="Ex: Decathlon..." oninput="filtrerVelos()"></div>
                    <div class="filter-group"><label>💰 Budget Max</label><input type="number" id="budgetVelo" placeholder="Ex: 1500" oninput="filtrerVelos()"></div>
                </div>
                <div class="grid-layout" id="veloGrid">{cartes_velos}</div>
            </div>
            
            <div id="sectionReparateurs" style="display: none;">
                <div class="filter-bar">
                    <div class="filter-group"><label>📍 Ville / Nom</label><input type="text" id="searchRep" placeholder="Ex: Paris..." oninput="filtrerReparateurs()"></div>
                    <div class="filter-group"><label>💶 Tarif Max</label><input type="number" id="tarifMaxRep" placeholder="Ex: 60" oninput="filtrerReparateurs()"></div>
                </div>
                <div class="grid-layout" id="reparateurGrid">{cartes_reparateurs}</div>
            </div>
        </div>

        <script>
            function switchTab(type) {{
                if(type === 'velos') {{
                    document.getElementById('sectionVelos').style.display = 'block';
                    document.getElementById('sectionReparateurs').style.display = 'none';
                    document.getElementById('btnVelos').classList.add('active');
                    document.getElementById('btnReparateurs').classList.remove('active');
                }} else {{
                    document.getElementById('sectionVelos').style.display = 'none';
                    document.getElementById('sectionReparateurs').style.display = 'block';
                    document.getElementById('btnVelos').classList.remove('active');
                    document.getElementById('btnReparateurs').classList.add('active');
                }}
            }}

            function filtrerVelos() {{
                const txt = document.getElementById('searchVelo').value.toLowerCase();
                const budget = parseFloat(document.getElementById('budgetVelo').value) || Infinity;
                const grid = document.getElementById('veloGrid');
                const cartes = Array.from(grid.getElementsByClassName('velo-card'));
                
                cartes.forEach(c => {{
                    const matchTxt = c.getAttribute('data-nom').includes(txt) || c.getAttribute('data-moteur').includes(txt);
                    const matchPrix = parseFloat(c.getAttribute('data-prix')) <= budget;
                    c.style.display = (matchTxt && matchPrix) ? "flex" : "none";
                }});
            }}

            function filtrerReparateurs() {{
                const txt = document.getElementById('searchRep').value.toLowerCase();
                const tarifMax = parseFloat(document.getElementById('tarifMaxRep').value) || Infinity;
                const grid = document.getElementById('reparateurGrid');
                const cartes = Array.from(grid.getElementsByClassName('reparateur-card'));
                
                cartes.forEach(c => {{
                    const matchTxt = c.getAttribute('data-nom').includes(txt) || c.getAttribute('data-ville').includes(txt);
                    const tarif = parseFloat(c.getAttribute('data-tarif'));
                    c.style.display = (matchTxt && (tarif === 0 || tarif <= tarifMax)) ? "flex" : "none";
                }});
            }}
        </script>
    </body>
    </html>
    """

# API Synchronisation (Utilisée par le Robot et par le Formulaire d'Admin)
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
        existe.nom, existe.prix, existe.moteur, existe.batterie, existe.description_ia = nom_f, prix_f, moteur_f, bat_f, desc_f
        if img_f: existe.image_url = img_f
    else:
        db.add(VeloDB(id=id_f, nom=nom_f, prix=prix_f, moteur=moteur_f, batterie=bat_f, description_ia=desc_f, image_url=img_f))
    
    db.commit()
    if est_form: return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return {"message": "Mis à jour avec succès"}

# -------------------------------------------------------------------------
# ESPACE ADMIN
# -------------------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Admin - VéloÉlec</title>
            <style>body{{font-family:sans-serif;background:#f4f7f6;padding:40px;}} .box{{background:white;padding:30px;max-width:500px;margin:0 auto;border-radius:8px;box-shadow:0 4px 10px rgba(0,0,0,0.05);}} input,textarea{{width:100%;padding:10px;margin-bottom:15px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;}} button{{background:#3498db;color:white;padding:12px;width:100%;border:none;border-radius:4px;font-weight:bold;cursor:pointer;}} label{{font-weight:bold;font-size:13px;display:block;margin-bottom:5px;color:#34495e;}}</style>
        </head>
        <body>
            <div class="box">
                <h2>⚙️ Ajouter ou Modifier un Vélo</h2>
                <form action="/api/ajouter-velo" method="POST">
                    <input type="hidden" name="robot_token_form" value="{ROBOT_TOKEN}">
                    
                    <label>ID unique du vélo (ex: decathlon-rockrider-e-expl-520-s)</label>
                    <input type="text" name="id" placeholder="ID pour écraser ou nouveau à créer" required>
                    
                    <label>Nom complet</label>
                    <input type="text" name="nom" placeholder="Ex: Decathlon Rockrider E-EXPL 520 S" required>
                    
                    <label>Prix (€)</label>
                    <input type="number" name="prix" required>
                    
                    <label>Moteur</label>
                    <input type="text" name="moteur">
                    
                    <label>Batterie</label>
                    <input type="text" name="batterie">
                    
                    <label>Lien URL de la vraie Photo (Copier/Coller)</label>
                    <input type="text" name="image_url" placeholder="https://site.com/photo.jpg">
                    
                    <label>Avis IA (Respecter le format // + et // -)</label>
                    <textarea name="description_ia" rows="5" required></textarea>
                    
                    <button type="submit">🚀 Enregistrer le vélo</button>
                </form>
                <a href="/" style="display:block; text-align:center; margin-top:15px; color:#95a5a6; text-decoration:none;">Retour au catalogue</a>
            </div>
        </body>
    </html>
    """