import os
from dotenv import load_dotenv
import firebase_admin
import json
from firebase_admin import credentials, firestore

load_dotenv()
# Path to your downloaded service account key JSON file
# Make sure this path is correct for where you saved the file!
service_account_json = {
    "type": os.getenv("type"),
    "project_id": os.getenv("project_id"),
    "private_key_id": os.getenv("private_key_id"),
    "private_key":os.getenv("private_key", "").replace("\\n", "\n"),
    "client_email": os.getenv("client_email"),
    "client_id": os.getenv("client_id"),
    "auth_uri": os.getenv("auth_uri"),
    "token_uri": os.getenv("token_uri"),
    "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
    "client_x509_cert_url": os.getenv("client_x509_cert_url"),
    "universe_domain": os.getenv("universe_domain")
}


# Initialize the Firebase Admin SDK
try:
    cred = credentials.Certificate(service_account_json)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully!")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    exit() # Exit if initialization fails, as you can't proceed without it

# Get a reference to your Firestore database
db = firestore.client()

def getDataBase():
    return db

print("Connected to Firestore!")