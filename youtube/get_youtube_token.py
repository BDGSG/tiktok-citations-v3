"""Script one-shot pour obtenir un token YouTube OAuth2.

Usage (en local) :
    pip install google-auth-oauthlib google-api-python-client
    python youtube/get_youtube_token.py

Ce script va :
1. Lire les credentials depuis "client cdj_youtube.json"
2. Ouvrir ton navigateur pour autoriser l'acces
3. Generer youtube_token.json
4. Tu devras copier ce fichier sur le serveur
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# pip install google-auth-oauthlib google-api-python-client
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes necessaires pour upload YouTube
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Charger le fichier client credentials
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET_FILE = PROJECT_ROOT / "client cdj_youtube.json"

if not CLIENT_SECRET_FILE.exists():
    print(f"Erreur: Fichier non trouve : {CLIENT_SECRET_FILE}")
    exit(1)

print(f"Credentials: {CLIENT_SECRET_FILE}")
print("Ouverture du navigateur pour l'autorisation YouTube...")
print("Si le navigateur ne s'ouvre pas, copie l'URL affichee.\n")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
credentials = flow.run_local_server(port=8080, prompt="consent")

# Sauvegarder le token
token_data = {
    "access_token": credentials.token,
    "refresh_token": credentials.refresh_token,
    "token_uri": credentials.token_uri,
    "client_id": credentials.client_id,
    "client_secret": credentials.client_secret,
    "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
    "expires_in": 3600,
    "obtained_at": datetime.now(timezone.utc).isoformat(),
    "expires_at": credentials.expiry.isoformat() if credentials.expiry else "",
}

output_path = Path(__file__).resolve().parent / "youtube_token.json"
with open(output_path, "w") as f:
    json.dump(token_data, f, indent=2)

print(f"\nToken sauvegarde dans : {output_path}")
print(f"Access token  : {credentials.token[:20]}...")
print(f"Refresh token : {credentials.refresh_token[:20]}...")
print(f"\nProchaine etape :")
print(f"  Copie ce fichier sur le serveur :")
print(f"  scp {output_path} root@82.25.117.199:/data/tiktok_citations_v3/youtube/youtube_token.json")
