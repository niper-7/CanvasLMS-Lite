import re
import json
import bcrypt
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
Assignmets_FILE = os.path.join(BASE_DIR, "data", "assignments.json")
# ---------- ID VALIDATION ----------

def is_valid_id(user_id):
    """Validates 8-digit ID and determines role"""
    if not re.fullmatch(r"\d{8}", user_id):
        return False, None

    if user_id.endswith("0000"):
        return True, "faculty"
    
    year = user_id[-4:]
    if year.isdigit() and 2022 <= int(year) <= 2028:
        return True, "student"
    
    return False, None

# ---------- PASSWORD VALIDATION ----------

def is_strong_password(password):
    """Checks password strength rules"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*]", password):
        return False
    return True

# ---------- PASSWORD HASHING ----------

def hash_password(password):
    """Hashes password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password_match(plain_password, hashed_password):
    """Verifies hashed password"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

# ---------- JSON DATA HELPERS ----------

def load_json(file_path):
    """Safely loads JSON data"""
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f)   
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_json(file_path, data):
    """Writes JSON data with indentation"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ---------- USER LOOKUP ----------

def get_user_by_id(user_id, file_path="data/users.json"):
    """Retrieves a user by ID"""
    users = load_json(file_path)
    for user in users:
        if user["id"] == user_id:
            return user
    return None
