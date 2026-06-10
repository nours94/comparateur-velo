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
                description_ia="Idéal pour débuter le VTT électrique à petit prix. Moteur arrière suffisant sur le plat, mais limité en forte pente."
            ),
            VeloDB(
                id="nakamura-e-crossover",
                nom="Intersport Nakamura E-Crossover",
                prix=1599,
                moteur="Moteur central Naka Hub One 60Nm",
                batterie="460 Wh",
                description_ia="Le meilleur rapport qualité/prix urbain actuel. Son moteur central de 60Nm est idéal pour franchir les côtes sans effort."
            )
        ]
        db.add_all(velos_init)
        db.commit()
    db.close()

# -------------------------------------------------------------------------
# ROUTES DU SITE
# -------------------------------------------------------------------------

# Page d'accueil Humains
@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    velos = db.query(VeloDB).all()
    lignes_velos = ""
    for velo in velos:
        lignes_velos += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #ddd; font-weight: bold;">{velo.nom}</td>
            <td style="padding: 12px; border-bottom: 1px solid #ddd; color: #2ecc71; font-weight: bold;">{velo.prix} €</td>
            <td style="padding: 12px; border-bottom: 1px solid #ddd; font-size: 0.9em;">{velo.moteur} <br><small style="color:#777">{velo.batterie}</small></td>
            <td style="padding: 12px; border-bottom: 1px solid #ddd; font-style: italic; font-size: 0.95em; color: #555;">{velo.description_ia}</td>
        </tr>
        """
    return f"""
    <html>
        <head>
            <title>Mon Comparateur Vélo</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }}
                .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background-color: #f4f6f7; padding: 12px; text-align: left; color: #34495e; }}
                .bot-banner {{ background-color: #e8f4fd; border-left: 4px solid #3498db; padding: 15px; margin-top: 30px; border-radius: 4px; }}
                .btn-admin {{ display: inline-block; background-color: #34495e; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-bottom: 15px; float: right;}}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="/admin" class="btn-admin">⚙️ Espace Admin</a>
                <h1>🚲 Mon Comparateur de Vélos Électriques</h1>
                <p>Bienvenue ! Les données ci-dessous proviennent d'une base de données SQLite :</p>
                <table>
                    <thead><tr><th>Modèle</th><th>Prix</th><th>Caractéristiques</th><th>L'avis de l'expert</th></tr></thead>
                    <tbody>{lignes_velos}</tbody>
                </table>
                <div class="bot-banner">
                    <strong>Version pour les IA :</strong> <a href="/llms.txt">/llms.txt</a>
                </div>
            </div>
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
                .note {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
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
                        <label>Avis de l'expert (Copier l'IA ou Avis Personnel)</label>
                        <textarea name="description_ia" placeholder="Colle l'avis généré par le robot ou écris ton propre retour d'expérience..." required></textarea>
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
# API MISE À JOUR : ACCEPTE LE ROBOT (JSON) ET LE FORMULAIRE MANUEL
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
    velo_json: VeloSchema = None # Pour intercepter le robot
):
    # ÉTAPE 1 : On détermine si la requête vient du Formulaire ou du Robot
    if robot_token_form:  # ---- PROVIENT DE LA PAGE ADMIN ----
        if robot_token_form != ROBOT_TOKEN:
            raise HTTPException(status_code=401, detail="Token d'administration invalide")
        
        id_final = id
        nom_final = nom
        prix_final = prix
        moteur_final = moteur
        batterie_final = batterie
        description_final = description_ia
        est_formulaire = True
        
    else:  # ---- PROVIENT DU ROBOT PYTHON (JSON) ----
        # Si FastAPI n'a pas pu valider le JSON automatiquement à cause du format Form, on le récupère manuellement
        if not velo_json:
            raise HTTPException(status_code=400, detail="Données invalides")
        
        id_final = velo_json.id
        nom_final = velo_json.nom
        prix_final = velo_json.prix
        moteur_final = velo_json.moteur
        batterie_final = velo_json.batterie
        description_final = velo_json.description_ia
        est_formulaire = False

    # ÉTAPE 2 : Insertion dans la base SQLite (Identique pour les deux)
    existe_deja = db.query(VeloDB).filter(VeloDB.id == id_final).first()
    if existe_deja:
        raise HTTPException(status_code=400, detail="Ce vélo est déjà enregistré en base de données.")
    
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
    
    # ÉTAPE 3 : Réponse personnalisée selon l'expéditeur
    if est_formulaire:
        # Si c'est un humain depuis l'admin, on le redirige proprement sur la page d'accueil pour voir son vélo en ligne !
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    else:
        # Si c'est ton script Python robot_ia.py, on renvoie le message JSON attendu
        return {"message": f"Vélo '{nom_final}' ajouté avec succès par le robot !"}