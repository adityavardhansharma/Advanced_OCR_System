import os
import json
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# --- MongoDB Atlas Configuration ---
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)


def get_user_by_email(email, mongo_db):
    """Retrieve a user by email from MongoDB."""
    try:
        return mongo_db.users.find_one({"email": email})
    except Exception as e:
        logger.error(f"Error retrieving user by email: {e}")
        return None


def get_user_by_id(user_id, mongo_db):
    """Retrieve a user by their ID from MongoDB."""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return mongo_db.users.find_one({"_id": user_id})
    except Exception as e:
        logger.error(f"Error retrieving user by ID: {e}")
        return None


def create_user(user_data, mongo_db):
    """Insert new user data into MongoDB."""
    try:
        result = mongo_db.users.insert_one(user_data)
        return result.inserted_id
    except Exception as e:
        logger.error(f"Error creating user in MongoDB: {e}")
        return None


def convert_mongo_to_supabase(data):
    """
    Convert MongoDB document to Supabase-compatible format.
    - Convert ObjectId to string
    - Convert datetime to ISO format
    - Remove MongoDB _id field
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Skip _id field as Supabase uses its own id
            if key == '_id':
                continue
            # Convert nested structures
            result[key] = convert_mongo_to_supabase(value)
        return result
    elif isinstance(data, list):
        return [convert_mongo_to_supabase(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


def store_test_result(user_id, test_data, mongo_db, supabase):
    """
    Store test results in both MongoDB and Supabase.

    The test document combines:
      • The parsed test data (from OCR or voice)
      • The registered user details from the user record
    """
    try:
        # Get user details from MongoDB
        user = get_user_by_id(user_id, mongo_db)
        if not user:
            logger.error(f"User not found with ID: {user_id}")
            return None, None

        # Prepare the test result document using the registered user details
        test_result = {
            "user_id": str(user_id),
            "registration_id": user.get("registration_id"),
            "user_name": user.get("name"),
            "user_email": user.get("email"),
            "user_age": str(user.get("age")),
            "user_gender": user.get("gender"),
            "test_data": test_data.get("tests", {}),  # Extract tests from the parsed data
            "timestamp": datetime.now(),
            "source": test_data.get("source", "image")  # default source
        }

        # Insert into MongoDB: use "reports" collection
        mongo_result = mongo_db.reports.insert_one(test_result)
        logger.info(f"Test result stored in MongoDB with ID: {mongo_result.inserted_id}")

        # Prepare the data for Supabase
        supabase_data = convert_mongo_to_supabase(test_result)

        # Get the Supabase user ID for the foreign key constraint
        supabase_user = supabase.table("users").select("id").eq("registration_id",
                                                                user.get("registration_id")).execute()
        if not supabase_user.data:
            logger.error(f"User not found in Supabase with registration_id: {user.get('registration_id')}")
            return mongo_result.inserted_id, None

        supabase_user_id = supabase_user.data[0]['id']
        supabase_data['user_id'] = supabase_user_id

        # Insert into Supabase (table: test_results)
        supabase_response = supabase.table("test_results").insert(supabase_data).execute()
        logger.info(f"Test result stored in Supabase")

        return mongo_result.inserted_id, supabase_response.data
    except Exception as e:
        logger.error(f"Error storing test result: {e}")
        return None, None


def get_user_test_results(user_id, mongo_db):
    """Retrieve all test results for a given user (from the 'reports' collection)."""
    try:
        results = list(mongo_db.reports.find({"user_id": str(user_id)}).sort("timestamp", -1))
        return results
    except Exception as e:
        logger.error(f"Error retrieving test results: {e}")
        return []
