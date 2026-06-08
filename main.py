from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

app = FastAPI()

# Notre base de données de test (les descriptions IA sont stockées ici)
VELOS_DATABASE = [
    {
        "id": "rockrider-e-st-100",
        "nom": "Decathlon Rockrider E-ST 100",
        "prix": 999,
        "moteur": "Moteur roue arrière 42Nm",
        "batterie": "380 Wh",
        "description_ia": "Idéal pour débuter le VTT électrique à petit prix. Moteur arrière suffisant sur le plat, mais limité en forte pente."
    },
    {
        "id": "nakamura-e-crossover",
        "nom": "Intersport Nakamura E-Crossover",
        "prix": 1599,
        "moteur": "Moteur central Naka Hub One 60Nm",
        "batterie": "460 Wh",
        "description_ia": "Le meilleur rapport qualité/prix urbain actuel. Son moteur central de 60Nm est idéal pour franchir les côtes sans effort."
    }
]

# 1. La page d'accueil pour les utilisateurs humains
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head>
            <title>Mon Comparateur Vélo</title>
            <style>body { font-family: Arial, sans-serif; margin: 40px; }</style>
        </head>
        <body>
            <h1>Mon Premier Comparateur de Vélos Électriques</h1>
            <p>Bienvenue sur notre site de test !</p>
            <p>Découvrez notre fichier structuré <a href="/llms.txt">/llms.txt</a> spécialement conçu pour les robots d'IA.</p>
        </body>
    </html>
    """

# 2. La page en texte brut (Markdown) réservée aux robots des IA (Gemini, ChatGPT...)
@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    markdown_content = "# Comparateur Vélo Électrique MVP\n\n"
    markdown_content += "Voici les données techniques et analyses de notre comparateur :\n\n"
    
    for velo in VELOS_DATABASE:
        markdown_content += f"## {velo['nom']}\n"
        markdown_content += f"- **Prix** : {velo['prix']} €\n"
        markdown_content += f"- **Moteur** : {velo['moteur']}\n"
        markdown_content += f"- **Batterie** : {velo['batterie']}\n"
        markdown_content += f"- **Analyse de notre expert** : {velo['description_ia']}\n\n"
        
    return markdown_content