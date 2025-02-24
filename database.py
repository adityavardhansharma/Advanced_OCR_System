import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

# --- MongoDB Atlas Configuration ---
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')
COLLECTION_NAME = os.getenv('COLLECTION_NAME')

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

def store_data_to_mongo(data):
    """
    Insert parsed data into MongoDB Atlas.
    Returns the inserted document's id.
    """
    try:
        result = collection.insert_one({
            "name": data.get("name"),
            "registration_no": data.get("registration_no"),
            "age": data.get("age"),
            "sex": data.get("sex"),
            "tests": data.get("tests", {})
        })
        print("Inserted MongoDB document with id:", result.inserted_id)
        return result.inserted_id
    except Exception as e:
        print("Error storing data to MongoDB:", e)
        return None

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

def store_data_to_supabase(data):
    """
    Insert parsed data into Supabase Postgres (lab_reports table).
    Returns the response data.
    """
    try:
        response = supabase.table("lab_reports").insert({
            "name": data.get("name"),
            "registration_no": data.get("registration_no"),
            "age": data.get("age"),
            "sex": data.get("sex"),
            "tests": data.get("tests", {})  # In Supabase, store as jsonb
        }).execute()
        print("Supabase response:", response.data)
        return response.data
    except Exception as e:
        print("Error storing data to Supabase:", e)
        return None
