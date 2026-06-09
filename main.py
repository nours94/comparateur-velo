from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse
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

# Définition de la table Vélo dans la base de données
class VeloDB(Base):
    __tablename__ = "velos"
    
    id = Column(String, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prix = Column(Integer, nullable=False)
    moteur = Column(String)
    batterie = Column(String)
    description_ia = Column(Text)

# Création de la table dans le fichier local velos.db s'il n'existe pas
Base.metadata.create_all(bind=engine)

# Fonction de dépendance pour ouvrir/fermer la session de base de données à chaque requête
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialisation automatique avec les données initiales si la base est vide
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
# ROUTES DE L'APPLICATION
# -------------------------------------------------------------------------

# 1. La page d'accueil pour les utilisateurs humains (lit les données depuis la BDD)
@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    # Récupération de tous les vélos enregistrés en base de données
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
            <title>Mon Comparateur Vélo (Mode BDD)</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }}
                .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background-color: #f4f6f7; padding: 12px; text-align: left; color: #34495e; }}
                .bot-banner {{ background-color: #e8f4fd; border-left: 4px solid #3498db; padding: 15px; margin-top: 30px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1> Mon Comparateur de Vélos Électriques</h1>
                <p>Bienvenue ! Les données ci-dessous proviennent désormais d'une base de données SQLite :</p>
                
                <table>
                    <thead>
                        <tr>
                            <th>Modèle</th>
                            <th>Prix</th>
                            <th>Caractéristiques</th>
                            <th>L'avis de l'expert</th>
                        </tr>
                    </thead>
                    <tbody>
                        {lignes_velos}
                    </tbody>
                </table>

                <div class="bot-banner">
                     <strong>Version pour les IA :</strong> Vous êtes un robot ou un LLM ? 
                    Consultez directement notre fichier structuré <a href="/llms.txt" style="color: #2980b9; font-weight: bold;">/llms.txt</a> pour extraire les données instantanément.
                </div>
            </div>
        </body>
    </html>
    """

# 2. La page en texte brut (Markdown) réservée aux robots des IA (lit les données depuis la BDD)
@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(db: Session = Depends(get_db)):
    # Récupération de tous les vélos pour l'affichage de l'IA
    velos = db.query(VeloDB).all()
    
    markdown_content = "# Comparateur Vélo Électrique MVP\n\n"
    markdown_content += "Voici les données techniques et analyses de notre comparateur :\n\n"
    
    for velo in velos:
        markdown_content += f"## {velo.nom}\n"
        markdown_content += f"- **Prix** : {velo.prix} €\n"
        markdown_content += f"- **Moteur** : {velo.moteur}\n"
        markdown_content += f"- **Batterie** : {velo.batterie}\n"
        markdown_content += f"- **Analyse de notre expert** : {velo.description_ia}\n\n"
        
    return markdown_content