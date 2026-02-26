import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from Salva.models import (
    User,
    TaskTemplate,
    TaskInstance,
    MatchAttempt,
    ClusterInstance,
    OrphanCluster,
    LearnedPattern,
)

load_dotenv()

# ============================================
# CONFIGURATION
# ============================================
ENV = os.getenv("ENV")  # "test" ou "prod"

DB_CONFIG = {
    "TEST": {
        "host": os.getenv("DB_TEST_HOST"),
        "port": os.getenv("DB_TEST_PORT"),
        "database": os.getenv("DB_TEST_NAME"),
        "user": os.getenv("DB_TEST_USER"),
        "password": os.getenv("DB_TEST_PASSWORD"),
    },
    "PROD": {
        "host": os.getenv("DB_PROD_HOST"),
        "port": os.getenv("DB_PROD_PORT"),
        "database": os.getenv("DB_PROD_NAME"),
        "user": os.getenv("DB_PROD_USER"),
        "password": os.getenv("DB_PROD_PASSWORD"),
    },
}


def get_database_url(env: str = None) -> str:
    """Construit l'URL de connexion MySQL pour l'environnement donné."""
    env = env or ENV
    config = DB_CONFIG.get(env)

    if not config:
        raise ValueError(f"Environnement inconnu : '{env}'. Utilise 'test' ou 'prod'.")

    return (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset=utf8mb4"
    )


def get_engine(env: str = None, echo: bool = False):
    """Crée le moteur SQLAlchemy pour l'environnement donné."""
    url = get_database_url(env)
    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_session(env: str = None) -> Session:
    """Retourne une session SQLModel."""
    engine = get_engine(env)
    return Session(engine)


# ============================================
# CRÉATION DES TABLES
# ============================================
def create_database(env: str = None, echo: bool = True):
    """Crée toutes les tables dans la base de données cible."""
    env = env or ENV
    engine = get_engine(env, echo=echo)

    print(f"Connexion à la base '{env}'...")
    print(f"URL : {get_database_url(env).replace(DB_CONFIG[env]['password'], '****')}")

    SQLModel.metadata.create_all(engine)

    print(f"Toutes les tables ont été créées avec succès sur '{env}'.")
    print("Tables créées :")
    for table_name in SQLModel.metadata.tables:
        print(f"  - {table_name}")


def drop_database(env: str = None, echo: bool = True):
    """Supprime toutes les tables (à utiliser avec précaution)."""
    env = env or ENV

    if env == "prod":
        confirm = input("⚠️  Vous allez supprimer la base de PRODUCTION. Tapez 'CONFIRM' : ")
        if confirm != "CONFIRM":
            print("Annulé.")
            return

    engine = get_engine(env, echo=echo)

    # Désactive les FK checks pour éviter les problèmes de dépendances circulaires
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table_name in SQLModel.metadata.tables:
            conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    print(f"Toutes les tables ont été supprimées sur '{env}'.")