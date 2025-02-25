import re
import logging
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from bson import ObjectId
from database import get_user_by_email, create_user, get_user_by_id

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_registration_id(db_collection):
    """Generate a unique registration ID in the format MRO1, MRO2, etc."""
    try:
        user_count = db_collection.count_documents({})
        return f"MRO{user_count + 1}"
    except Exception as e:
        logger.error(f"Error generating registration ID: {e}")
        # Fallback to a timestamp-based ID if counting fails
        return f"MRO{int(uuid.uuid4().hex[:6], 16)}"


def validate_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"


def validate_mobile(mobile):
    return re.match(r'^\d{10}$', mobile) is not None


def prepare_user_for_supabase(user_data):
    """
    Prepare user data for Supabase by removing MongoDB-specific fields
    and ensuring data types match the Supabase schema.
    """
    supabase_user = user_data.copy()

    # Remove MongoDB _id if present
    if '_id' in supabase_user:
        supabase_user.pop('_id')

    # Ensure age is an integer
    if 'age' in supabase_user and supabase_user['age'] is not None:
        try:
            supabase_user['age'] = int(supabase_user['age'])
        except (ValueError, TypeError):
            supabase_user['age'] = None

    return supabase_user


def register_user(name, email, age, gender, mobile, password, mongo_db, supabase):
    try:
        existing_user = get_user_by_email(email, mongo_db)
        if existing_user:
            return False, "Email already registered"

        if not validate_email(email):
            return False, "Invalid email format"

        valid_password, password_msg = validate_password(password)
        if not valid_password:
            return False, password_msg

        if not validate_mobile(mobile):
            return False, "Invalid mobile number format"

        reg_id = generate_registration_id(mongo_db.users)
        hashed_password = generate_password_hash(password)

        user_data = {
            "registration_id": reg_id,
            "name": name,
            "email": email,
            "age": int(age),
            "gender": gender,
            "mobile": mobile,
            "password": hashed_password
        }

        # Insert into MongoDB
        mongo_result = create_user(user_data, mongo_db)
        if not mongo_result:
            return False, "Error creating user in MongoDB"

        # Prepare data for Supabase
        supabase_user_data = prepare_user_for_supabase(user_data)

        # Insert into Supabase
        try:
            supabase_result = supabase.table("users").insert(supabase_user_data).execute()
            if not supabase_result.data:
                logger.error("Failed to insert user into Supabase")
                # Consider rolling back MongoDB insertion here
                return False, "Error creating user in Supabase"
        except Exception as e:
            logger.error(f"Supabase insertion error: {e}")
            # Consider rolling back MongoDB insertion here
            return False, f"Error creating user in Supabase: {str(e)}"

        return True, reg_id
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return False, f"Registration error: {str(e)}"


def login_user(email, password, mongo_db):
    try:
        user = get_user_by_email(email, mongo_db)
        if not user:
            return False, "Email not found"
        if not check_password_hash(user['password'], password):
            return False, "Incorrect password"

        session['user_id'] = str(user['_id'])
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        session['registration_id'] = user['registration_id']

        return True, "Login successful"
    except Exception as e:
        logger.error(f"Error in login_user: {e}")
        return False, f"Login error: {str(e)}"


def logout_user():
    session.clear()
    return True


def is_logged_in():
    return 'user_id' in session


def get_logged_in_user(mongo_db):
    if 'user_id' not in session:
        return None
    return get_user_by_id(session['user_id'], mongo_db)
