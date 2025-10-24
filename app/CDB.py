import chromadb
from datetime import datetime, timedelta, timezone
import time
from dotenv import load_dotenv
import os
from collections import defaultdict
from Ollama import Ollama

load_dotenv()
print(os.getenv("CHROMA_HOST"), os.getenv("CHROMA_PORT"))
class DBC :
    chroma_client = chromadb.HttpClient(host=os.getenv("CHROMA_HOST"), port=int(os.getenv("CHROMA_PORT")))
    
    def get_collection(self, collection_name : str) -> chromadb.Collection :
        print(self.chroma_client.list_collections())
        return self.chroma_client.get_or_create_collection(collection_name)

class DBCCollection(DBC):
    def __init__(self, collection_name : str):
        super().__init__()
        self.collection : chromadb.Collection = self.get_collection(collection_name)

    def query_collection(self, question: str, n_results: int = 3) -> chromadb.QueryResult :
        # Calcul des bornes en UTC
        now_utc = datetime.now(timezone.utc)
        seven_days_ago_utc = now_utc - timedelta(days=7)

        # Conversion en timestamp float
        start_ts = seven_days_ago_utc.timestamp()
        end_ts = now_utc.timestamp()

        print(start_ts, end_ts)
        # Query Chroma avec bornes $gt et $lt
        return self.collection.query(
            query_texts=[question],
            n_results=n_results,
            where={
                "$and": [
                    {"topic": "TECHNOLOGY"},
                    {"timestamp": {"$gt": start_ts}},
                ]
            }
        )

    def merge_article_chunks(self, results):
        merged = defaultdict(lambda: {"topic": None, "timestamp": None, "texts": []})
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            src = meta["source"]
            merged[src]["topic"] = meta.get("topic")
            merged[src]["timestamp"] = meta.get("timestamp")
            merged[src]["texts"].append(doc)

        articles = []
        for src, data in merged.items():
            articles.append({
                "source": src,
                "topic": data["topic"],
                "timestamp": data["timestamp"],
                "text": " ".join(data["texts"]),  # fusionne et limite
            })
        return articles
    
    def set_article_informations(self) :
        self.news = ""

        res = self.query_collection("technology and artificial inteligence in the world", n_results=10)
        art = self.merge_article_chunks(res)
        
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            self.news = self.news + f"source: {meta["source"]} \n"
            self.news = self.news + f"Document : {doc}\n\n"

    def Get_Article_JSON(self) :
        return {'article resume' : self.news}
