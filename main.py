from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

app = FastAPI()

# -------------------------------------------------------------------------
# CONFIGURATION DE LA BASE DE DONNÉES (SQLite)
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

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Sécurité : Clé secrète pour autoriser uniquement TON robot ou TON formulaire à ajouter des vélos
API_KEY_NAME = "X-Robot-Token"
ROBOT_TOKEN = "super_secret_token_123"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verifier_robot(api_key: str = Depends(api_key_header)):
    if api_key != ROBOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Accès refusé : Token robot invalide"
        )
    return api_key

# Modèle de données attendu pour l'ajout d'un vélo via JSON (Robot)
class VeloSchema(BaseModel):
    id: str
    nom: str
    prix: int
    moteur: str
    batterie: str
    description_ia: str

@app.on_event("startup")
def init_db():
    db = SessionLocal()
    if db.query(VeloDB).count() == 0:
        velos_init = [
            VeloDB(
                id="rockrider-e-st-100",
                nom="Decathlon Rockrider E-ST 100",
                prix=999,
                moteur="Moteur roue arrière 42Nm",
                batterie="380 Wh",
                description_ia="Idéal pour débuter le VTT électrique à petit prix. // + Prix très accessible, cadre robuste, position confortable. // - Moteur arrière limité en forte pente, autonomie juste pour les longues sorties."
            ),
            VeloDB(
                id="nakamura-e-crossover",
                nom="Intersport Nakamura E-Crossover",
                prix=1599,
                moteur="Moteur central Naka Hub One 60Nm",
                batterie="460 Wh",
                description_ia="Le meilleur rapport qualité/prix urbain actuel. // + Moteur central coupleux (60Nm), équipement complet, bonne autonomie. // - Esthétique un peu classique, poids important."
            )
        ]
        db.add_all(velos_init)
        db.commit()
    db.close()

# -------------------------------------------------------------------------
# ROUTES DU SITE
# -------------------------------------------------------------------------

# Page d'accueil Humains (Style cartes + filtres JS)
@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    cartes_velos = ""
    
    for velo in velos:
        # Découpage de l'avis de l'expert si présence de "//"
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
            
        cartes_velos += f"""
        <div class="velo-card" data-prix="{velo.prix}" data-nom="{velo.nom.lower()}" data-moteur="{velo.moteur.lower()}">
            <div class="velo-header">
                <span class="bike-icon">🚲</span>
                <h2 class="velo-title">{velo.nom}</h2>
            </div>
            
            <div class="velo-price-tag">{velo.prix} €</div>
            
            <div class="velo-specs">
                <div class="spec-item">
                    <span class="spec-icon">⚡</span>
                    <div>
                        <strong>Moteur</strong>
                        <p>{velo.moteur}</p>
                    </div>
                </div>
                <div class="spec-item">
                    <span class="spec-icon">🔋</span>
                    <div>
                        <strong>Batterie</strong>
                        <p>{velo.batterie}</p>
                    </div>
                </div>
            </div>
            
            <div class="velo-review">
                <strong>📋 L'avis de l'expert :</strong>
                {pros_cons_section}
            </div>
        </div>
        """
        
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VéloÉlec - Le Comparateur Moderne</title>
        <style>
            :root {{
                --primary: #3498db;
                --primary-dark: #2980b9;
                --dark: #2c3e50;
                --bg: #f5f7fa;
                --card-bg: #ffffff;
                --text: #34495e;
                --success: #2ecc71;
            }}
            body {{ font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 0; }}
            .navbar {{ background-color: var(--dark); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .navbar-brand {{ color: white; font-size: 22px; font-weight: bold; text-decoration: none; }}
            .btn-admin {{ background-color: var(--primary); color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; font-weight: bold; font-size: 14px; transition: all 0.3s; }}
            .btn-admin:hover {{ background-color: var(--primary-dark); transform: translateY(-2px); }}
            .main-container {{ max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
            .hero-section {{ text-align: center; margin-bottom: 30px; }}
            .hero-section h1 {{ color: var(--dark); font-size: 36px; margin-bottom: 10px; }}
            .hero-section p {{ color: #7f8c8d; font-size: 18px; margin: 0; }}
            
            /* BARRE DE FILTRES STYLE PROFESSIONNEL */
            .filter-bar {{
                background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);
                margin-bottom: 30px; display: flex; flex-wrap: wrap; gap: 20px; align-items: center; justify-content: space-between; border: 1px solid #e2e8f0;
            }}
            .filter-group {{ display: flex; align-items: center; gap: 10px; }}
            .filter-group label {{ font-weight: bold; font-size: 14px; color: var(--dark); }}
            .filter-bar input, .filter-bar select {{ padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; background-color: #f8fafc; }}
            .filter-bar input:focus, .filter-bar select:focus {{ border-color: var(--primary); background-color: #fff; }}
            
            .velo-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 30px; margin-top: 20px; }}
            .velo-card {{ background: var(--card-bg); border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); padding: 25px; display: flex; flex-direction: column; transition: all 0.3s; border: 1px solid rgba(0,0,0,0.02); }}
            .velo-card:hover {{ transform: translateY(-5px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }}
            .velo-header {{ display: flex; align-items: flex-start; gap: 12px; margin-bottom: 15px; }}
            .bike-icon {{ font-size: 24px; background: #e8f4fd; padding: 8px; border-radius: 12px; }}
            .velo-title {{ font-size: 20px; color: var(--dark); margin: 0; line-height: 1.3; }}
            .velo-price-tag {{ align-self: flex-start; background-color: var(--success); color: white; padding: 6px 16px; font-weight: bold; font-size: 18px; border-radius: 30px; margin-bottom: 20px; }}
            .velo-specs {{ background: #f8fafc; border-radius: 12px; padding: 15px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 12px; }}
            .spec-item {{ display: flex; align-items: center; gap: 12px; }}
            .spec-icon {{ font-size: 18px; }}
            .spec-item strong {{ font-size: 12px; text-transform: uppercase; color: #95a5a6; display: block; }}
            .spec-item p {{ margin: 2px 0 0 0; font-size: 14px; color: var(--dark); font-weight: 500; }}
            .velo-review {{ border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: auto; }}
            .velo-review strong {{ font-size: 14px; color: var(--dark); display: block; margin-bottom: 6px; }}
            .review-text {{ margin: 0 0 15px 0; font-style: italic; font-size: 14px; color: #555; line-height: 1.5; }}
            .pros-cons-container {{ display: flex; flex-direction: column; gap: 10px; font-size: 13px; background: #fafbfc; padding: 12px; border-radius: 8px; }}
            .pros-list, .cons-list {{ margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 5px; }}
            .bot-banner {{ background-color: #e8f4fd; border-left: 4px solid var(--primary); padding: 15px; margin-top: 50px; border-radius: 8px; font-size: 14px; }}
            .bot-banner a {{ color: var(--primary-dark); font-weight: bold; text-decoration: none; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <a href="/" class="navbar-brand">⚡ VéloÉlec</a>
            <a href="/admin" class="btn-admin">⚙️ Espace Admin</a>
        </nav>
        
        <div class="main-container">
            <div class="hero-section">
                <h1>🚲 Fiches Comparatives des Vélos Électriques</h1>
                <p>Bienvenue ! Les données ci-dessous proviennent d'une base de données SQLite :</p>
            </div>
            
            <div class="filter-bar">
                <div class="filter-group">
                    <label for="search">🔍 Rechercher</label>
                    <input type="text" id="search" placeholder="Ex: Decathlon, Rockrider..." oninput="filtrerLesVelos()">
                </div>
                
                <div class="filter-group">
                    <label for="budget">💰 Budget Max</label>
                    <input type="number" id="budget" placeholder="Ex: 1500" oninput="filtrerLesVelos()">
                    <span style="font-size: 14px; color: #7f8c8d;">€</span>
                </div>
                
                <div class="filter-group">
                    <label for="tri">➡️ Trier par</label>
                    <select id="tri" onchange="filtrerLesVelos()">
                        <option value="defaut">Pertinence</option>
                        <option value="prix-croissant">Prix : du - cher au + cher</option>
                        <option value="prix-decroissant">Prix : du + cher au - cher</option>
                    </select>
                </div>
            </div>
            
            <div class="velo-grid" id="veloGrid">
                {cartes_velos}
            </div>
            
            <div class="bot-banner">
                <strong>Version pour les IA :</strong> <a href="/llms.txt">/llms.txt</a>
            </div>
        </div>

        <script>
            function filtrerLesVelos() {{
                const tRecherche = document.getElementById('search').value.toLowerCase();
                const budgetMax = parseFloat(document.getElementById('budget').value) || Infinity;
                const triOption = document.getElementById('tri').value;
                
                const grid = document.getElementById('veloGrid');
                const cartes = Array.from(grid.getElementsByClassName('velo-card'));
                
                cartes.forEach(carte => {{
                    const nom = carte.getAttribute('data-nom');
                    const moteur = carte.getAttribute('data-moteur');
                    const prix = parseFloat(carte.getAttribute('data-prix'));
                    
                    const correspondRecherche = nom.includes(tRecherche) || moteur.includes(tRecherche);
                    const correspondBudget = prix <= budgetMax;
                    
                    if (correspondRecherche && correspondBudget) {{
                        carte.style.display = "flex";
                    }} else {{
                        carte.style.display = "none";
                    }}
                }});
                
                if (triOption === 'prix-croissant') {{
                    cartes.sort((a, b) => parseFloat(a.getAttribute('data-prix')) - parseFloat(b.getAttribute('data-prix')));
                    cartes.forEach(carte => grid.appendChild(carte));
                }} else if (triOption === 'prix-decroissant') {{
                    cartes.sort((a, b) => parseFloat(b.getAttribute('data-prix')) - parseFloat(a.getAttribute('data-prix')));
                    cartes.forEach(carte => grid.appendChild(carte));
                }}
            }}
        </script>
    </body>
    </html>
    """

# -------------------------------------------------------------------------
# NOUVEAUTÉ : PAGE DU DASHBOARD ADMIN
# -------------------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return f"""
    <html>
        <head>
            <title>Dashboard Admin - Comparateur Vélo</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }}
                .admin-container {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); width: 100%; max-width: 600px; }}
                h1 {{ color: #2c3e50; margin-bottom: 20px; font-size: 24px; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                .form-group {{ margin-bottom: 15px; }}
                label {{ display: block; margin-bottom: 5px; font-weight: 600; color: #34495e; }}
                input[type="text"], input[type="number"], textarea {{ width: 100%; padding: 10px; border: 1px solid #bdc3c7; border-radius: 6px; box-sizing: border-box; font-size: 14px; }}
                textarea {{ height: 120px; resize: vertical; }}
                .btn-submit {{ background-color: #3498db; color: white; border: none; padding: 12px 20px; font-size: 16px; font-weight: bold; border-radius: 6px; cursor: pointer; width: 100%; transition: background 0.2s; }}
                .btn-submit:hover {{ background-color: #2980b9; }}
                .btn-back {{ display: block; text-align: center; margin-top: 15px; color: #7f8c8d; text-decoration: none; font-size: 0.9em; }}
                .note {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; background: #fff8db; padding: 8px; border-radius: 4px; border-left: 3px solid #f1c40f; line-height: 1.4; }}
            </style>
        </head>
        <body>
            <div class="admin-container">
                <h1>🚲 Ajouter un Vélo manuellement</h1>
                <form action="/api/ajouter-velo" method="POST">
                    <input type="hidden" name="robot_token_form" value="{ROBOT_TOKEN}">
                    
                    <div class="form-group">
                        <label>Identifiant Unique (ID)</label>
                        <input type="text" name="id" placeholder="Ex: rockrider-e-st100" required>
                        <div class="note">Uniquement des lettres minuscules, chiffres et tirets (-).</div>
                    </div>
                    <div class="form-group">
                        <label>Nom complet du vélo</label>
                        <input type="text" name="nom" placeholder="Ex: Decathlon Rockrider E-ST 100" required>
                    </div>
                    <div class="form-group">
                        <label>Prix indicatif (€)</label>
                        <input type="number" name="prix" placeholder="Ex: 899" required>
                    </div>
                    <div class="form-group">
                        <label>Caractéristiques du moteur</label>
                        <input type="text" name="moteur" placeholder="Ex: Moteur central Naka E-Power Max, 100 Nm" required>
                    </div>
                    <div class="form-group">
                        <label>Capacité de la batterie</label>
                        <input type="text" name="batterie" placeholder="Ex: 460 Wh" required>
                    </div>
                    <div class="form-group">
                        <label>Avis de l'expert & Points Forts/Faibles</label>
                        <textarea name="description_ia" placeholder="Phrase d'introduction générale. // + Point fort 1, Point fort 2 // - Point faible 1" required></textarea>
                        <div class="note">
                            <strong>💡 Format d'affichage Pro :</strong> Écris une phrase, puis sépare avec <code>//</code> en mettant <code>+</code> pour les qualités et <code>-</code> pour les défauts (sépare par des virgules).
                        </div>
                    </div>
                    <button type="submit" class="btn-submit">🚀 Mettre en ligne instantanément</button>
                </form>
                <a href="/" class="btn-back">⬅️ Retourner sur le site public</a>
            </div>
        </body>
    </html>
    """

# Page LLM (Markdown)
@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    markdown_content = "# Comparateur Vélo Électrique MVP\n\n"
    for velo in velos:
        markdown_content += f"## {velo.nom}\n- **Prix** : {velo.prix} €\n- **Moteur** : {velo.moteur}\n- **Batterie** : {velo.batterie}\n- **Analyse** : {velo.description_ia}\n\n"
    return markdown_content

# -------------------------------------------------------------------------
# API : AJOUT ET LOGIQUE DE MISE A JOUR (UPSERT)
# -------------------------------------------------------------------------
@app.post("/api/ajouter-velo", status_code=status.HTTP_201_CREATED)
async def ajouter_velo(
    db: Session = Depends(get_db),
    id: str = Form(None),
    nom: str = Form(None),
    prix: int = Form(None),
    moteur: str = Form(None),
    batterie: str = Form(None),
    description_ia: str = Form(None),
    robot_token_form: str = Form(None),
    velo_json: VeloSchema = None 
):
    if robot_token_form: 
        if robot_token_form != ROBOT_TOKEN:
            raise HTTPException(status_code=401, detail="Token d'administration invalide")
        id_final = id
        nom_final = nom
        prix_final = prix
        moteur_final = moteur
        batterie_final = batterie
        description_final = description_ia
        est_formulaire = True
        
    else: 
        if not velo_json:
            raise HTTPException(status_code=400, detail="Données invalides")
        id_final = velo_json.id
        nom_final = velo_json.nom
        prix_final = velo_json.prix
        moteur_final = velo_json.moteur
        batterie_final = velo_json.batterie
        description_final = velo_json.description_ia
        est_formulaire = False

    # Correction de ton problème de blocage : logique d'écrase-et-remplace (UPSERT)
    existe_deja = db.query(VeloDB).filter(VeloDB.id == id_final).first()
    if existe_deja:
        # Au lieu de renvoyer une erreur 400, on met à jour les données !
        existe_deja.nom = nom_final
        existe_deja.prix = prix_final
        existe_deja.moteur = moteur_final
        existe_deja.batterie = batterie_final
        existe_deja.description_ia = description_final
        db.commit()
        message_retour = f"Vélo '{nom_final}' mis à jour avec succès !"
    else:
        nouveau_velo = VeloDB(
            id=id_final,
            nom=nom_final,
            prix=prix_final,
            moteur=moteur_final,
            batterie=batterie_final,
            description_ia=description_final
        )
        db.add(nouveau_velo)
        db.commit()
        message_retour = f"Vélo '{nom_final}' ajouté avec succès !"
    
    if est_formulaire:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return {"message": message_retour}