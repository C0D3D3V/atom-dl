# Basisimage
FROM python:3.11-slim

# Define build-time arguments for user ID and group ID
ARG PUID=621
ARG PGID=1000

# Create a user group and a user to run the application
RUN groupadd -g ${PGID} -r atom-dl && useradd -u ${PUID} -r -g atom-dl -m -s /bin/bash atom-dl

# Setze Arbeitsverzeichnis innerhalb des Containers
WORKDIR /app

# Kopiere den gesamten aktuellen Code in das Arbeitsverzeichnis
COPY . .

# Installiere Abhängigkeiten
RUN pip install .

# Change ownership of the application directory
RUN chown -R atom-dl:atom-dl /app
RUN chown -R atom-dl:atom-dl /home/atom-dl/

# Switch to the non-root user
USER atom-dl

RUN mkdir -p /home/atom-dl/.local/share/atom-dl
RUN mkdir -p /home/atom-dl/.config/atom-dl


# Startbefehl für das Python-Skript
CMD ["atom-dl", "-h"]