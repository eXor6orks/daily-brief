import chromadb
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

import os
from collections import defaultdict

CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = os.getenv("CHROMA_PORT")

"""
    Class for connect to vector database (Chroma). 
"""
class DBC :
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=int(CHROMA_PORT))
    
    def get_collection(self, collection_name : str) -> chromadb.Collection :
        print(self.chroma_client.list_collections())
        return self.chroma_client.get_or_create_collection(collection_name)

"""
    This class is an exemple of class for manage a collection in database.

    For exemple, this class manage Artciles Collection in my database.
    My collection stock few articles automatically. With distance research,
    wa can have the most near artciles from the question.

    It's possible to update it if you have a different collection. 
"""
class DBCCollection(DBC):
    def __init__(self, collection_name : str):
        super().__init__()
        self.collection : chromadb.Collection = self.get_collection(collection_name)

        self.news : str = ""

    def query_collection(self, question: str, n_results: int = 3) -> chromadb.QueryResult :
        # Calcul des bornes en UTC
        now_utc = datetime.now(timezone.utc)
        seven_days_ago_utc = now_utc - timedelta(days=7)

        # Conversion en timestamp float
        start_ts = seven_days_ago_utc.timestamp()

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
    
    def set_article_informations(self, question : str) :
        res = self.query_collection(question, n_results=10)
        
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            self.news = self.news + f"source: {meta["source"]} \n"
            self.news = self.news + f"Document : {doc}\n\n"

    def Get_Article_JSON(self) :
        return {'article resume' : self.news}
