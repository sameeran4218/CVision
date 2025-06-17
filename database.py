import os
import pymongo
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

# Initialize MongoDB connection with error handling
try:
    client = MongoClient(os.environ.get('MONGO_URI'), server_api=ServerApi('1'))
    # Test the connection
    client.admin.command('ping')
    db = client['CVDataStorage']
    users = db["user"]
    print(f'Successfully connected to MongoDB!')
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    client = None
    db = None
    users = None

# function to add company-wise,role-wise user details like name,cv, cv score ,strengths, weakness and suggestions
def addUserData(company: str, role: str, user_details: dict) -> None:
    if users is None:
        print("MongoDB connection not available")
        return
    
    try:
        # step 1: check if company exists:
        company_doc = users.find_one({"company": company})
        if not company_doc:
            # Insert new company with role and user
            users.insert_one({
                "company": company,
                "roles": [
                    {
                        "role": role,
                        "users": [user_details]
                    }
                ]
            })
            print("Company, role, and user added.")
        else:
            # step 2: check if role exists
            role_exists = any(r['role'] == role for r in company_doc['roles'])

            if role_exists:
                # Role exists, add user to existing role
                for r in company_doc['roles']:
                    if r['role'] == role:
                        r['users'].append(user_details)
                        break

                # Update the document in the database
                users.update_one(
                    {"company": company},
                    {"$set": {"roles": company_doc['roles']}}
                )
                print("User added to existing role.")
            else:
                # Role doesn't exist, add new role with user
                company_doc['roles'].append({
                    "role": role,
                    "users": [user_details]
                })

                # Update the document in the database
                users.update_one(
                    {"company": company},
                    {"$set": {"roles": company_doc['roles']}}
                )
                print("New role and user added to existing company.")
    except Exception as e:
        print(f"Error in addUserData: {e}")

def getCandidates(company, role=None):
    if users is None:
        print("MongoDB connection not available")
        return []
    
    try:
        if role:
            # Get only users for the specified role, sorted by cv_score (desc)
            pipeline = [
                {"$match": {"company": company}},
                {"$unwind": "$roles"},
                {"$match": {"roles.role": role}},
                {"$unwind": "$roles.users"},
                {"$replaceRoot": {"newRoot": "$roles.users"}},
                {"$sort": {"cv_score": -1}}
            ]
            candidates = list(users.aggregate(pipeline))
        else:
            # Get all users for the company, sorted by cv_score (desc)
            pipeline = [
                {"$match": {"company": company}},
                {"$unwind": "$roles"},
                {"$unwind": "$roles.users"},
                {"$replaceRoot": {"newRoot": "$roles.users"}},
                {"$sort": {"cv_score": -1}}
            ]
            candidates = list(users.aggregate(pipeline))
        return candidates
    except Exception as e:
        print(f"Error in getCandidates: {e}")
        return []

# 1) Fetch all suggestions for a specific user
def get_user_suggestions(user_name: str):
    if users is None:
        print("MongoDB connection not available")
        return ""
    
    try:
        pipeline = [
            {"$unwind": "$roles"},
            {"$unwind": "$roles.users"},
            {"$match": {"roles.users.name": user_name}},
            {"$project": {"_id": 0, "suggestions": "$roles.users.Suggestions"}}
        ]

        cursor = users.aggregate(pipeline)
        all_suggestions = []
        for doc in cursor:
            suggestions = doc.get("suggestions", [])
            if isinstance(suggestions, list):
                all_suggestions.extend(suggestions)  # flatten
            elif isinstance(suggestions, str):
                all_suggestions.append(suggestions)

        return ' '.join(all_suggestions)
    except Exception as e:
        print(f"Error in get_user_suggestions: {e}")
        return ""
