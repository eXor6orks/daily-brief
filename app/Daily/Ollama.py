import requests
import json
from datetime import datetime

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"

def serialize_data(data):
    def convert(obj):
        if isinstance(obj, (dict, list)):
            return {k: convert(v) for k, v in obj.items()} if isinstance(obj, dict) else [convert(i) for i in obj]
        elif hasattr(obj, "isoformat"):
            return obj.isoformat()
        else:
            return obj
    return convert(data)

class Ollama:
    def __init__(self, warm: bool = True, warm_prompt: str = "Warm model"):
        # Utilise une session persistante pour réutiliser la connexion HTTP et éviter certains surcoûts
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.model = MODEL

        # Optionnel : lancer un warm-up simple pour forcer le chargement du modèle une seule fois
        if warm:
            try:
                # demande courte et silencieuse pour précharger le modèle sur le serveur Ollama
                self._warm_model(warm_prompt)
            except Exception as e:
                # ne bloque pas l'exécution si le warm-up échoue ; affiche juste le warning
                print(f"[Ollama] Warm-up failed: {e}")

    def _warm_model(self, prompt: str):
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        # timeout plus long pour donner le temps au serveur de charger le modèle GPU si nécessaire
        resp = self.session.post(OLLAMA_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        # on ignore la réponse détaillée; l'objectif est juste de charger le modèle côté serveur
        return
    
    def _post(self, payload: dict) -> str:
        resp = self.session.post(OLLAMA_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def query(self, data):
        data_serialized = serialize_data(data)

        prompt = f"""
        Tu es un assistant personnel qui rédige un résumé quotidien clair et utile pour un ingénieur informatique.

        Voici mes données du jour :
        - Calendrier : {json.dumps(data_serialized.get('calendars', {}), ensure_ascii=False, indent=2)}
        - Météo : {json.dumps(data_serialized.get('weather', {}), ensure_ascii=False, indent=2)}
        - Résumé d'article parue récémment : {json.dumps(data_serialized.get('articles', {}), ensure_ascii=False, indent=2)}

        Fais un résumé concis sous forme de texte, agréable à lire pour le matin à partir des informations précédentes. 
        N'hésite pas à détailler des informations à propos des articles.
        """

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
    
    def resume_article(self, data):
        prompt = f"""
        Voici plusieurs articles récents sur la technologie et l'intelligence artificielle :
        {data}
        
        Tu es un ingénieur expert en IA et en systèmes informatiques.

        Ta mission :
        - Identifier UNIQUEMENT les 2 à 3 articles qui apportent de vraies informations nouvelles et pertinentes.
        - Ces informations peuvent concerner :
        • Un nouveau modèle d'IA ou une technologie innovante
        • Une avancée scientifique ou technique concrète
        • Un nouveau produit, framework ou outil
        • Une stratégie ou décision d'entreprise ayant un impact notable sur le domaine technologique

        Pour chaque article retenu :
        - Résume les points clés en 2 à 4 phrases claires et précises.
        - Mets en avant les aspects techniques ou stratégiques (modèles, frameworks, entreprises, enjeux).

        Si aucun article n'apporte d'information réellement utile ou nouvelle, indique-le explicitement :
        "Aucune nouveauté technologique ou information pertinente trouvée dans les articles récents."

        Garde un ton professionnel, clair et synthétique — comme un ingénieur qui prépare un daily brief pour son équipe.            
        """

        payload = {
            "model": "gemma3:1b",
            "prompt": prompt,
            "stream": False,
            "max_tokens": 256,
            "temperature": 0.2
        }

        return self._post(payload)

