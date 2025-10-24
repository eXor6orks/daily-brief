from datetime import datetime, timezone
from CDB import DBCCollection  # ton code actuel

def convert_iso_to_timestamp(collection):
    print("Debut conversion !")
    all_items = collection.get(include=["documents", "metadatas"])
    docs = all_items["documents"]
    metas = all_items["metadatas"]
    ids = all_items["ids"]  # ids sont disponibles ici automatiquement

    for doc, meta, id_ in zip(docs, metas, ids):
        ts = meta.get("timestamp")
        if ts and isinstance(ts, str):
            try:
                # Convertit ISO -> float
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                meta["timestamp"] = dt.timestamp()

                # Supprime uniquement cet item via son id
                collection.delete(ids=[id_])
                # Réinsère avec la nouvelle metadata
                collection.add(documents=[doc], metadatas=[meta], ids=[id_])
            except Exception as e:
                print(f"⚠️ Erreur conversion: {e} pour {ts}")

    print("✅ Conversion des timestamps terminée !")

# Exemple d'utilisation
c = DBCCollection("article")
convert_iso_to_timestamp(c.collection)