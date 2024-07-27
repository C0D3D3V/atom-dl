# Basisimage
FROM python:3.11-slim

# Setze Arbeitsverzeichnis innerhalb des Containers
WORKDIR /app

# Kopiere den gesamten aktuellen Code in das Arbeitsverzeichnis
COPY . .

# Installiere Abhängigkeiten
RUN pip install .

# Startbefehl für das Python-Skript
CMD ["atom-dl", "-h"]