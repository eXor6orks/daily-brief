FROM python:3.13.3-slim

# Définir le dossier de travail
WORKDIR /usr/src/app

# Copier et installer les dépendances en premier (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install cryptography

# Copier le code et le .env
COPY app/ .
COPY .env.prod .env

# Lancer le script au démarrage du container
CMD ["python", "scheduler.py"]