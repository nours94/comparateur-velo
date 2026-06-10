from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
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

# Table existante pour les Vélos
class VeloDB(Base):
    __tablename__ = "velos"
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prix = Column(Integer, nullable=False)
    moteur = Column(String)
    batterie = Column(String)
    description_ia = Column(Text)

# NOUVELLE Table pour les Réparateurs
class ReparateurDB(Base):
    __tablename__ = "reparateurs"
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    ville = Column(String, nullable=False)
    adresse = Column(String)
    telephone = Column(String)
    note = Column(Float, default=4.5)
    tarif_horaire = Column(Integer)  # Tarif indicatif de main d'œuvre
    specialites = Column(String)     # Ex: "Moteur Bosch, Shimano, Électricité, Freins hydrauliques"

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Sécurité
API_KEY_NAME = "X-Robot-Token"
ROBOT_TOKEN = "super_secret_token_123"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verifier_robot(api_key: str = Depends(api_key_header)):
    if api_key != ROBOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token robot invalide")
    return api_key

class VeloSchema(BaseModel):
    id: str
    nom: str
    prix: int
    moteur: str
    batterie: str
    description_ia: str

# NOUVEAU Schéma pour l'API Réparateur
class ReparateurSchema(BaseModel):
    id: str
    nom: str
    ville: str
    adresse: str = None
    telephone: str = None
    note: float = 4.5
    tarif_horaire: int = None
    specialites: str = None

@app.on_event("startup")
def init_db():
    db = SessionLocal()
    # Init Vélos
    if db.query(VeloDB).count() == 0:
        velos_init = [
            VeloDB(
                id="rockrider-e-st-100",
                nom="Decathlon Rockrider E-ST 100",
                prix=999,
                moteur="Moteur roue arrière 42Nm",
                batterie="380 Wh",
                description_ia="Idéal pour débuter le VTT électrique à petit prix. // + Prix très accessible, cadre robuste. // - Autonomie juste."
            ),
            VeloDB(
                id="nakamura-e-crossover",
                nom="Intersport Nakamura E-Crossover",
                prix=1599,
                moteur="Moteur central Naka Hub One 60Nm",
                batterie="460 Wh",
                description_ia="Le meilleur rapport qualité/prix urbain actuel. // + Moteur central coupleux, équipement complet. // - Poids important."
            )
        ]
        db.add_all(velos_init)
        db.commit()
        
    # Init Réparateurs (Données de test)
    if db.query(ReparateurDB).count() == 0:
        reparateurs_init = [
            ReparateurDB(
                id="repar-elec-paris",
                nom="Atelier Cyclo Élec Paris",
                ville="Paris",
                adresse="15 Rue de Rivoli, 75001 Paris",
                telephone="01 42 33 44 55",
                note=4.8,
                tarif_horaire=65,
                specialites="Moteurs Bosch, Shimano Steps, Diagnostics batteries, Électricité VAE"
            ),
            ReparateurDB(
                id="clinique-du-velo-lyon",
                nom="La Clinique du Vélo",
                ville="Lyon",
                adresse="84 Avenue Jean Jaurès, 69007 Lyon",
                telephone="04 72 80 90 10",
                note=4.6,
                tarif_horaire=55,
                specialites="Révision générale, Freins hydrauliques, Moteurs roues (Bafang)"
            )
        ]
        db.add_all(reparateurs_init)
        db.commit()
    db.close()

# -------------------------------------------------------------------------
# ROUTES DU SITE PUBLIC
# -------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    reparateurs = db.query(ReparateurDB).all()
    
    # Génération HTML des cartes Vélos
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

        pros_cons_section = f"<p class='review-text'>{avis_general}</p>"
        if points_forts_html or points_faibles_html:
            pros_cons_section += f'<div class="pros-cons-container">'
            if points_forts_html: pros_cons_section += f'<ul class="pros-list">{points_forts_html}</ul>'
            if points_faibles_html: pros_cons_section += f'<ul class="cons-list">{points_faibles_html}</ul>'
            pros_cons_section += '</div>'
        
        cartes_velos += f"""
        <div class="velo-card" data-prix="{velo.prix}" data-nom="{velo.nom.lower()}" data-moteur="{velo.moteur.lower()}">
            <div class="velo-header">
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

    # NOUVEAU : Génération HTML des cartes Réparateurs
    cartes_reparateurs = ""
    for rep in reparateurs:
        cartes_reparateurs += f"""
        <div class="reparateur-card" data-ville="{rep.ville.lower()}" data-nom="{rep.nom.lower()}" data-tarif="{rep.tarif_horaire or 0}">
            <div class="velo-header">
                <span class="card-icon">🔧</span>
                <h2 class="card-title">{rep.nom}</h2>
            </div>
            <div class="price-tag status-blue">{rep.tarif_horaire if rep.tarif_horaire else '--'} €/h</div>
            <div class="rating-tag">⭐ {rep.note} / 5</div>
            <div class="card-specs" style="background: #fdf6ec;">
                <div class="spec-item">
                    <span class="spec-icon">📍</span>
                    <div><strong>Localisation</strong><p>{rep.adresse} ({rep.ville})</p></div>
                </div>
                <div class="spec-item">
                    <span class="spec-icon">📞</span>
                    <div><strong>Contact</strong><p>{rep.telephone if rep.telephone else 'Non renseigné'}</p></div>
                </div>
            </div>
            <div class="card-review" style="border-top: 1px dashed #e67e22;">
                <strong>🛠️ Spécialités :</strong>
                <p style="font-size: 13px; color: #555; margin: 5px 0 0 0;">{rep.specialites}</p>
            </div>
        </div>
        """
        
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VéloÉlec - Le Comparateur Global</title>
        <style>
            :root {{
                --primary: #3498db;
                --primary-dark: #2980b9;
                --dark: #2c3e50;
                --bg: #f5f7fa;
                --card-bg: #ffffff;
                --text: #34495e;
                --success: #2ecc71;
                --orange: #e67e22;
            }}
            body {{ font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 0; }}
            .navbar {{ background-color: var(--dark); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .navbar-brand {{ color: white; font-size: 22px; font-weight: bold; text-decoration: none; }}
            .btn-admin {{ background-color: var(--primary); color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; font-weight: bold; font-size: 14px; transition: all 0.3s; }}
            .btn-admin:hover {{ background-color: var(--primary-dark); transform: translateY(-2px); }}
            .main-container {{ max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
            
            /* SYSTÈME D'ONGLETS */
            .tabs-container {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }}
            .tab-btn {{ padding: 12px 25px; border: none; font-size: 16px; font-weight: bold; border-radius: 30px; cursor: pointer; transition: all 0.3s; background: #e2e8f0; color: var(--text); }}
            .tab-btn.active {{ background: var(--dark); color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            
            /* BARRES DE FILTRES */
            .filter-bar {{
                background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);
                margin-bottom: 30px; display: flex; flex-wrap: wrap; gap: 20px; align-items: center; justify-content: space-between; border: 1px solid #e2e8f0;
            }}
            .filter-group {{ display: flex; align-items: center; gap: 10px; }}
            .filter-group label {{ font-weight: bold; font-size: 14px; color: var(--dark); }}
            .filter-bar input, .filter-bar select {{ padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; background-color: #f8fafc; }}
            
            .grid-layout {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 30px; margin-top: 20px; }}
            
            /* STYLE COMMUN DES CARTES */
            .velo-card, .reparateur-card {{ background: var(--card-bg); border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); padding: 25px; display: flex; flex-direction: column; transition: all 0.3s; border: 1px solid rgba(0,0,0,0.02); }}
            .velo-card:hover, .reparateur-card:hover {{ transform: translateY(-5px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }}
            .velo-header {{ display: flex; align-items: flex-start; gap: 12px; margin-bottom: 15px; }}
            .card-icon {{ font-size: 24px; background: #e8f4fd; padding: 8px; border-radius: 12px; }}
            .card-title {{ font-size: 20px; color: var(--dark); margin: 0; line-height: 1.3; }}
            .price-tag {{ align-self: flex-start; background-color: var(--success); color: white; padding: 6px 16px; font-weight: bold; font-size: 18px; border-radius: 30px; margin-bottom: 15px; }}
            .price-tag.status-blue {{ background-color: var(--primary); }}
            .rating-tag {{ font-size: 14px; font-weight: bold; color: #f1c40f; margin-bottom: 15px; }}
            .card-specs {{ background: #f8fafc; border-radius: 12px; padding: 15px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 12px; }}
            .spec-item {{ display: flex; align-items: center; gap: 12px; }}
            .spec-icon {{ font-size: 18px; }}
            .spec-item strong {{ font-size: 12px; text-transform: uppercase; color: #95a5a6; display: block; }}
            .spec-item p {{ margin: 2px 0 0 0; font-size: 14px; color: var(--dark); font-weight: 500; }}
            .card-review {{ border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: auto; }}
            .card-review strong {{ font-size: 14px; color: var(--dark); display: block; }}
            .review-text {{ margin: 5px 0 15px 0; font-style: italic; font-size: 14px; color: #555; line-height: 1.5; }}
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
                    <div class="filter-group">
                        <label>🔍 Rechercher</label>
                        <input type="text" id="searchVelo" placeholder="Ex: Decathlon, Rockrider..." oninput="filtrerVelos()">
                    </div>
                    <div class="filter-group">
                        <label>💰 Budget Max</label>
                        <input type="number" id="budgetVelo" placeholder="Ex: 1500" oninput="filtrerVelos()">
                    </div>
                    <div class="filter-group">
                        <label>➡️ Trier par</label>
                        <select id="triVelo" onchange="filtrerVelos()">
                            <option value="defaut">Pertinence</option>
                            <option value="prix-croissant">Prix : du - cher au + cher</option>
                        </select>
                    </div>
                </div>
                <div class="grid-layout" id="veloGrid">{cartes_velos}</div>
            </div>
            
            <div id="sectionReparateurs" style="display: none;">
                <div class="filter-bar">
                    <div class="filter-group">
                        <label>📍 Ville / Nom</label>
                        <input type="text" id="searchRep" placeholder="Ex: Paris, Lyon, Atelier..." oninput="filtrerReparateurs()">
                    </div>
                    <div class="filter-group">
                        <label>💶 Tarif Horaire Max</label>
                        <input type="number" id="tarifMaxRep" placeholder="Ex: 60" oninput="filtrerReparateurs()">
                    </div>
                </div>
                <div class="grid-layout" id="reparateurGrid">{cartes_reparateurs}</div>
            </div>
        </div>

        <script>
            // Logique de basculement d'onglets
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

            // Filtres Vélos
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
                if (document.getElementById('triVelo').value === 'prix-croissant') {{
                    cartes.sort((a, b) => parseFloat(a.getAttribute('data-prix')) - parseFloat(b.getAttribute('data-prix')));
                    cartes.forEach(c => grid.appendChild(c));
                }}
            }}

            // Filtres Réparateurs
            function filtrerReparateurs() {{
                const txt = document.getElementById('searchRep').value.toLowerCase();
                const tarifMax = parseFloat(document.getElementById('tarifMaxRep').value) || Infinity;
                const grid = document.getElementById('reparateurGrid');
                const cartes = Array.from(grid.getElementsByClassName('reparateur-card'));
                
                cartes.forEach(c => {{
                    const matchTxt = c.getAttribute('data-nom').includes(txt) || c.getAttribute('data-ville').includes(txt);
                    const tarif = parseFloat(c.getAttribute('data-tarif'));
                    const matchTarif = tarif === 0 || tarif <= tarifMax;
                    c.style.display = (matchTxt && matchTarif) ? "flex" : "none";
                }});
            }}
        </script>
    </body>
    </html>
    """

# -------------------------------------------------------------------------
# API ET FORMULAIRES DE MISE A JOUR (AJOUT UNIQUE SANS DOUBLONS / UPSERT)
# -------------------------------------------------------------------------

# Route d'écriture pour les Réparateurs (gère le JSON du robot ou un Formulaire)
@app.post("/api/ajouter-reparateur", status_code=status.HTTP_201_CREATED)
async def ajouter_reparateur(
    db: Session = Depends(get_db),
    id: str = Form(None),
    nom: str = Form(None),
    ville: str = Form(None),
    adresse: str = Form(None),
    telephone: str = Form(None),
    note: float = Form(None),
    tarif_horaire: int = Form(None),
    specialites: str = Form(None),
    robot_token_form: str = Form(None),
    rep_json: ReparateurSchema = None
):
    if robot_token_form:
        if robot_token_form != ROBOT_TOKEN:
            raise HTTPException(status_code=401, detail="Token invalide")
        id_f, nom_f, ville_f, adr_f, tel_f, note_f, tarif_f, spec_f = id, nom, ville, adresse, telephone, note, tarif_horaire, specialites
        est_form = True
    else:
        if not rep_json: raise HTTPException(status_code=400, detail="Données invalides")
        id_f, nom_f, ville_f, adr_f, tel_f, note_f, tarif_f, spec_f = rep_json.id, rep_json.nom, rep_json.ville, rep_json.adresse, rep_json.telephone, rep_json.note, rep_json.tarif_horaire, rep_json.specialites
        est_form = False

    existe = db.query(ReparateurDB).filter(ReparateurDB.id == id_f).first()
    if existe:
        existe.nom, existe.ville, existe.adresse, existe.telephone, existe.note, existe.tarif_horaire, existe.specialites = nom_f, ville_f, adr_f, tel_f, note_f, tarif_f, spec_f
    else:
        nouveau = ReparateurDB(id=id_f, nom=nom_f, ville=ville_f, adresse=adr_f, telephone=tel_f, note=note_f, tarif_horaire=tarif_f, specialites=spec_f)
        db.add(nouveau)
    
    db.commit()
    if est_form: return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return {"message": "Réparateur synchronisé avec succès !"}

# Laisse tes autres routes @app.post("/api/ajouter-velo") et @app.get("/admin") telles quelles !