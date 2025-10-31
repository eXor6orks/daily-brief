import requests
import json
import datetime

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
MODEL_RESUME = "gemma3:1b"

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

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.model = MODEL

        # Optionnal : run warm-up to force the loading of model once
        if warm:
            try:
                # little ask for Ollama model
                self._warm_model(warm_prompt)
            except Exception as e:
                # Don't stop the process, just print the warnings
                print(f"[Ollama] Warm-up failed: {e}")

    def _warm_model(self, prompt: str):
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        # timeout more longer for stay time to server to load model on GPU
        resp = self.session.post(OLLAMA_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        # The response is useless
        return
    
    def _post(self, payload: dict) -> str:
        resp = self.session.post(OLLAMA_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "")

    """
    This function return the main Text generation from LLM model and print it
    on the terminal.
    """
    def query(self, data):
        data_serialized = serialize_data(data)

        prompt = f"""
        You are a personal assistant that writes a clear and useful daily summary for a software engineer.

        date of today : {datetime.datetime.now()}

        Here are today's data:
        - Calendar: {json.dumps(data_serialized.get('calendars', {}), ensure_ascii=False, indent=2)}
        - Weather: {json.dumps(data_serialized.get('weather', {}), ensure_ascii=False, indent=2)}
        - Recent articles summary: {json.dumps(data_serialized.get('articles', {}), ensure_ascii=False, indent=2)}

        Create a short, readable morning briefing from this information.
        Focus on key insights and briefly expand on interesting tech or AI news.
        """

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": True
        }

        with self.session.post(OLLAMA_API_URL, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            print("\n--- Daily Brief ---\n")
            full_text = ""
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    text_piece = chunk.get("response", "")
                    print(text_piece, end="", flush=True)
                    full_text += text_piece
            print("\n\n--- End of Brief ---\n")
        return full_text
    
    """
    Is a simplify summarizer for resume the main informations between few articles.
    """
    def resume_article(self, data):
        prompt = f"""
        Here are several recent articles about technology and artificial intelligence:
        {data}
        
        You are an expert software engineer specializing in AI and systems design.

        Your task:
        - Identify ONLY 2 to 3 articles that bring genuinely new and relevant information.
        - Such information can include:
          • A new AI model or innovative technology
          • A concrete scientific or technical advancement
          • A new product, framework, or tool
          • A strategic or business decision with major impact on the tech field

        For each selected article:
        - Summarize the key insights in 2 to 4 clear, precise sentences.
        - Highlight the technical or strategic aspects (models, frameworks, companies, implications).

        If none of the articles provide any meaningful or novel information, say so explicitly:
        "No significant or noteworthy technological updates found in the recent articles."

        Keep the tone professional, concise, and informative — like an engineer writing a morning brief for their team.
        """

        payload = {
            "model": MODEL_RESUME,
            "prompt": prompt,
            "stream": False,
            "max_tokens": 256,
            "temperature": 0.2
        }

        return self._post(payload)

