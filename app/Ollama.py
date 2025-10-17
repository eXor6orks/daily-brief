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
    def __init__(self):
        pass

    def query(self, data):
        data_serialized = serialize_data(data)

        prompt = f"""
        Tu es un assistant personnel qui rédige un résumé quotidien clair et utile.

        Voici mes données du jour :
        - Calendrier : {json.dumps(data_serialized.get('calendars', {}), ensure_ascii=False, indent=2)}
        - Météo : {json.dumps(data_serialized.get('weather', {}), ensure_ascii=False, indent=2)}

        Fais un résumé concis sous forme de texte, agréable à lire pour le matin à partir des informations précédentes. 
        """

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
