import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()
# Path to your downloaded service account key JSON file
# Make sure this path is correct for where you saved the file!
SERVICE_ACCOUNT_KEY_PATH = r"C:\Users\Yash Sinha\Downloads\vacuole-ff665-firebase-adminsdk-fbsvc-bd601d70b2.json"

# Initialize the Firebase Admin SDK
try:
    # print(SERVICE_ACCOUNT_KEY_PATH)
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
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