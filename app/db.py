from Salva.database import create_database, drop_database
import os
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV")
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gestion de la base de données DailyBrief")
    parser.add_argument(
        "--action",
        choices=["create", "drop", "recreate"],
        help="Action à effectuer : create, drop, ou recreate (drop + create)",
    )
    parser.add_argument(
        "--env",
        choices=["test", "prod"],
        default=None,
        help="Environnement cible (défaut : variable ENV ou 'test')",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Afficher les requêtes SQL exécutées",
    )

    args = parser.parse_args()
    target_env = args.env or ENV

    if args.action == "create":
        create_database(env=target_env, echo=args.echo)

    elif args.action == "drop":
        drop_database(env=target_env, echo=args.echo)

    elif args.action == "recreate":
        drop_database(env=target_env, echo=args.echo)
        create_database(env=target_env, echo=args.echo)