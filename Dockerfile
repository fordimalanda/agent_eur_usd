# On part de l'image officielle qui contient déjà MT5, Wine et l'API Python
FROM jsfrnc/mt5-docker-api:latest

# On se place dans le dossier de travail
WORKDIR /app

# On copie notre fichier de dépendances et on les installe
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# On copie tout notre code (dossier agent, main.py, etc.)
COPY . .

# La commande par défaut (sera écrasée par docker-compose)
CMD ["python", "main.py"]