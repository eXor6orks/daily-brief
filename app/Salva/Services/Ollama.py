import requests
import json
import datetime
from typing import Optional

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"
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
    
    def _parse_json_response(self, raw: str) -> Optional[dict]:
        """Extrait et parse le JSON depuis la réponse du LLM."""
        cleaned = raw.strip()

        # Retirer les blocs markdown ```json ... ```
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"Échec parsing JSON LLM: {e}\nRéponse brute:\n{raw[:500]}")
            return None

    def _format_free_slots(self, free_slots: list) -> str:
        """Formate les créneaux libres pour affichage lisible.
        
        Args:
            free_slots: liste de dicts [{'Début': '06:00', 'Fin': '09:00'}, ...]
        
        Returns:
            str formatée, ex: "06:00 à 09:00 (180 minutes)\n18:30 à 22:00 (210 minutes)"
        """
        if not free_slots:
            return "Aucun créneau libre"
        
        formatted_lines = []
        for slot in free_slots:
            try:
                debut = slot.get("Début", "")
                fin = slot.get("Fin", "")
                
                # Parser les heures pour calculer la durée
                h_debut, m_debut = map(int, debut.split(":"))
                h_fin, m_fin = map(int, fin.split(":"))
                
                min_debut = h_debut * 60 + m_debut
                min_fin = h_fin * 60 + m_fin
                
                # Gérer le cas où fin est le jour suivant (ex: 22:00 > 06:00)
                if min_fin <= min_debut:
                    min_fin += 24 * 60
                
                duration = min_fin - min_debut
                formatted_lines.append(f"{debut} à {fin} ({duration} minutes)")
            except Exception as e:
                print(f"Erreur formattage créneau {slot}: {e}")
                formatted_lines.append(f"{slot.get('Début', '?')} à {slot.get('Fin', '?')}")
        
        return "\n  ".join(formatted_lines)

    def _format_event_exist(self, event_exist : list[dict]) -> str :
        txt = ""
        for event in event_exist :
            txt += f"  - {event['Titre']}, {event['Debut']} à {event['Fin']}\n"
        return txt

    def generate_schedule(self, context: dict, mode: str = "day") -> Optional[dict]:
        """Génère un planning à partir du contexte ScheduleContext.

        Args:
            context: dict produit par ScheduleContext.build()
            mode: "day" pour un seul jour, "week" pour la semaine

        Returns:
            dict avec "tasks" (liste d'events à créer) et "reasoning" (explication)
        """
        context_serialized = serialize_data(context)

        if mode == "day":
            prompt = self._build_day_prompt(context_serialized)
        else:
            prompt = self._build_optimized_prompt(context_serialized)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 1.0,
        }

        raw = self._post(payload)
        result = self._parse_json_response(raw)

        if not result:
            print("Le LLM n'a pas retourné un JSON valide.")
            return None

        # Valider la structure
        if "tasks" not in result:
            print(f"Réponse LLM sans clé 'tasks': {result}")
            return None

        print(f"Planning généré : {len(result['tasks'])} tâche(s)")
        return result
    
    def _build_optimized_prompt(self, context: dict) -> str:
        return f"""Tu es un assistant de productivité intelligent. Tu dois optimiser la journée de l'utilisateur.

## CONTEXTE

Date : 2026-02-23 (lundi)

PROGRAMME ACTUEL :
  - "Travail" 8:45 à 18:30
  - "Rendez-vois médecins" 19:00 à 20:00 (60min)
  - "Sport en salle" 7:00 à 8:30 (90min)
  - "Faire les courses" 20:00 à 20:45 (45min)

PREFERENCES UTILISATEUR :
  - 15 minutes minimum entre chaque taches
  - Maximum 5 tâches par jour

Optimiser le programme actuel afin qu'il soit le plus réalisable possible.
Fait bien attention à ne jamais déplacer des tâches dans les créneau indisponible.

## FORMAT DE RÉPONSE

Réponds UNIQUEMENT avec un JSON valide, sans texte avant ni après :

```json
{{
    "tasks": [
        {{
            "title": "Nom de la tâche",
            "scheduled_start": "2026-02-19T07:00:00+00:00",
            "scheduled_end": "2026-02-19T08:30:00+00:00",
            "description": "Description courte optionnelle"
        }}
    ],
    "reasoning": "Explication courte de tes choix d'optimisation"
}}
```

Si aucune tâche n'est à optimiser, réponds:
```json
{{
    "tasks": [],
    "reasoning": "La journée semble être optimiser."
}}
```"""
    
    def _build_day_prompt(self, context: dict) -> str:
        # Formater les créneaux libres s'ils sont fournis
        slots_text = ""
        if context['time_unabled']:
            slots_text = self._format_free_slots(context['time_unabled'])
        else:
            slots_text = "Aucun créneau libre fourni"
        
        return f"""Tu es un assistant de productivité intelligent. Tu dois planifier la journée de l'utilisateur.

## CONTEXTE

Date : {context['Day_date']} ({context['week_day']})

PROGRAMME ACTUEL :
{self._format_event_exist(context['existing_events'])}

CRÉNEAUX LIBRES (tu ne peux utiliser QUE ces horaires) :
  {slots_text}

TÂCHES À PLACER (maximum 5) :
  - "Faire les courses" durée=60min préférence=Soir

Place chaque tâche dans un créneau libre. 
Adapte toi au Programme actuel pour placer les taches.

## FORMAT DE RÉPONSE

Réponds UNIQUEMENT avec un JSON valide, sans texte avant ni après :

```json
{{
    "tasks": [
        {{
            "title": "Nom de la tâche",
            "template_id": 2,
            "scheduled_start": "2026-02-19T07:00:00+00:00",
            "scheduled_end": "2026-02-19T08:30:00+00:00",
            "description": "Description courte optionnelle",
            "priority": 4
        }}
    ],
    "reasoning": "Explication courte de tes choix de planification"
}}
```

Si aucune tâche à planifier ou qu'il est impossible de placer la tâcher si il n'y a pas de créneau disponible
OU que cela est vraiment incohérent avec l'attente de l'utilisateur, réponds:
```json
{{
    "tasks": [],
    "reasoning": "Aucune tâche récurrente n'est prévue pour ce jour."
}}
```"""
    
    def review_schedule(self, context: dict) -> Optional[dict]:
        """Contrôle le planning existant et propose des réorganisations si nécessaire.

        Returns:
            dict avec "keep" (inchangés), "move" (à déplacer), "add" (à ajouter), "cancel" (à annuler)
        """
        context_serialized = serialize_data(context)

        prompt = f"""Tu es un assistant de productivité. Tu dois CONTRÔLER le planning existant de la journée et proposer des ajustements si nécessaire.

## CONTEXTE

Date : {context_serialized['target_date']} ({context_serialized['day_of_week']})

### Préférences
{json.dumps(context_serialized['preferences'], ensure_ascii=False, indent=2)}

### Planning actuel de la journée
{json.dumps(context_serialized['existing_events'], ensure_ascii=False, indent=2)}

### Habitudes
{json.dumps(context_serialized['habits'], ensure_ascii=False, indent=2)}

## TA MISSION

Analyse le planning actuel et détermine :
1. Les tâches bien placées → "keep"
2. Les tâches à déplacer (conflit horaire, meilleur créneau) → "move"
3. Les tâches manquantes à ajouter → "add"
4. Les tâches en doublon ou non pertinentes → "cancel"

Si le planning est déjà bon, retourne des listes vides pour move/add/cancel.

## FORMAT DE RÉPONSE

Réponds UNIQUEMENT avec un JSON valide :

```json
{{
    "keep": ["Réunion projet", "Sport"],
    "move": [
        {{
            "title": "Tâche à déplacer",
            "current_start": "14:00",
            "new_start": "2026-02-19T16:00:00+00:00",
            "new_end": "2026-02-19T17:00:00+00:00",
            "reason": "Conflit avec la réunion"
        }}
    ],
    "add": [
        {{
            "title": "Tâche manquante",
            "template_id": 2,
            "scheduled_start": "2026-02-19T07:00:00+00:00",
            "scheduled_end": "2026-02-19T08:30:00+00:00",
            "priority": 4
        }}
    ],
    "cancel": [
        {{
            "title": "Tâche en doublon",
            "reason": "Déjà planifiée"
        }}
    ],
    "reasoning": "Le planning était presque complet, j'ai ajouté le sport du matin."
}}
```"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2,
        }

        raw = self._post(payload)
        return self._parse_json_response(raw)


