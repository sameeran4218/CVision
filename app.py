# Import packages
import os
import dotenv
import time
from flask import Flask,render_template,request,jsonify
from flask_wtf import FlaskForm
from wtforms import StringField,SubmitField,FileField
from wtforms.validators import DataRequired,Email
from flask_wtf.file import FileField, FileAllowed, FileRequired
from werkzeug.utils import secure_filename
import threading
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from database import get_user_suggestions
from llm import summarize_suggestions
import uuid
# Import functions
from utilities import *

# Load environment variables
dotenv.load_dotenv()

app = Flask(__name__)

# create secret key to restrict access to form
app.config['SECRET_KEY']=os.environ.get('FLASK_SECRET_KEY')
# intilize the uploads folder to upload CV's
app.config['UPLOADS_FOLDER'] = 'uploads'

# Ensure uploads directory exists
os.makedirs(app.config['UPLOADS_FOLDER'], exist_ok=True)

# Connect to MongoDB with error handling
try:
    client = MongoClient(os.environ.get('MONGO_URI'), server_api=ServerApi('1'))
    # Test the connection
    client.admin.command('ping')
    db = client["CVDataStorage"]
    collection = db["user"]
    print("MongoDB connection successful")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    client = None
    db = None
    collection = None

# create a form class
class jobDescForm(FlaskForm):
    companyName=StringField('Company Name',validators=[DataRequired()])
    jobRole=StringField('Job Role',validators=[DataRequired()])
    jobDesc=StringField('Job Description',validators=[DataRequired()])
    submit=SubmitField('Submit')

class userUploadForm(FlaskForm):
    userName=StringField('User Name',validators=[DataRequired()])
    userEmail=StringField('User Email',validators=[Email()])
    userRole=StringField('Job Role',validators=[DataRequired()])
    userCV=FileField('Upload Resume (pdf)',validators=[FileRequired(),
                     FileAllowed(['pdf'],'PDF files only!')])
    submit=SubmitField('Upload')

@app.route('/user', methods=['GET', 'POST'])
def user():
    form = userUploadForm()
    suggestion_summary = None

    if form.validate_on_submit():
        try:
            userName = form.userName.data.strip()
            userEmail = form.userEmail.data
            userRole = form.userRole.data
            cv = form.userCV.data

            filename = secure_filename(cv.filename)
            file_path = os.path.join(app.config['UPLOADS_FOLDER'], filename)
            cv.save(file_path)

            # Start threaded resume processing
            thread1 = threading.Thread(target=async_Workflow, args=(file_path, userName))
            thread1.start()

            # Poll MongoDB for suggestions, max 10 seconds
            timeout = 10
            interval = 1
            elapsed = 0
            suggestions = []

            while elapsed < timeout:
                suggestions = get_user_suggestions(userName)
                if suggestions:
                    break
                time.sleep(interval)
                elapsed += interval

            suggestion_summary = summarize_suggestions(suggestions) if suggestions else "Suggestions are not ready yet. Please try again shortly."

        except Exception as e:
            print(f"Error in user route: {e}")
            suggestion_summary = "An error occurred while processing your request."

    return render_template(
        'user.html',
        form=form,
        summary=suggestion_summary  # pass to template
    )

# async function to handle the complete workflow
def async_Workflow(file_path,userName):
    try:
        workFlow(file_path,userName)
    except Exception as e:
        print(f"Error in async_Workflow: {e}")

# Recruiter's Page
@app.route('/recruiter', methods=['GET', 'POST'])
def recruiter():
    form = jobDescForm()
    companyName = jobRole = jobDesc = None
    if form.validate_on_submit():
        try:
            companyName = form.companyName.data
            jobRole = form.jobRole.data
            jobDesc = form.jobDesc.data
            # generate unique user id
            unique_id=str(uuid.uuid4())

            # Once receiving data, pass it on to store it in the vector database.
            # Launch a background time to process asynchronously and avoid delays
            thread=threading.Thread(target=async_storeVectorDB,args=(companyName,jobRole,jobDesc,unique_id))
            thread.start()

            form.companyName.data = form.jobRole.data = form.jobDesc.data = ''
        except Exception as e:
            print(f"Error in recruiter route: {e}")
            
    return render_template('recruiter.html',
                           companyName=companyName,
                           jobRole=jobRole,
                           jobDesc=jobDesc,
                           form=form)

# async function to pass data to vector store
def async_storeVectorDB(company:str,role:str,desc:str,id:str)->None:
    try:
        storeVectorDB(company=company,role=role,job_desc=desc,id=id)
    except Exception as e:
        print(f"Error in async_storeVectorDB: {e}")

@app.route("/")
def index():
    try:
        # Check if MongoDB is available
        if collection is None:
            return render_template("dashboard.html", companies=[], error="Database connection unavailable")
        
        companies = collection.distinct("company")
        return render_template("dashboard.html", companies=companies)
    except Exception as e:
        print(f"Error in index route: {e}")
        # Fallback if MongoDB is down
        return render_template("dashboard.html", companies=[], error=str(e))

@app.route("/get_companies")
def get_companies():
    try:
        if collection is None:
            return jsonify({"error": "Database connection unavailable"}), 500
            
        companies = collection.distinct("company")
        return jsonify(companies)
    except Exception as e:
        print(f"Error in get_companies: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_roles")
def get_roles():
    company = request.args.get("company")
    if not company:
        return jsonify([])

    try:
        if collection is None:
            return jsonify({"error": "Database connection unavailable"}), 500
            
        doc = collection.find_one({"company": company})
        roles = [role['role'] for role in doc.get("roles", [])] if doc else []
        return jsonify(roles)
    except Exception as e:
        print(f"Error in get_roles: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_users")
def get_users():
    company = request.args.get("company")
    role = request.args.get("role")

    if not company or not role:
        return jsonify([])

    try:
        if collection is None:
            return jsonify({"error": "Database connection unavailable"}), 500
            
        doc = collection.find_one({"company": company})
        if not doc:
            return jsonify([])

        matched_users = []
        for r in doc.get("roles", []):
            if r["role"] == role:
                for user in r.get("users", []):
                    matched_users.append({
                        "role": r["role"],
                        "name": user.get("name", "N/A").strip(),
                        "fit_score": user.get("Fit Score", "N/A"),
                        "strengths": ", ".join(user.get("Strengths", [])),
                        "weaknesses": ", ".join(user.get("Weaknesses", [])),
                        "suggestions": ", ".join(user.get("Suggestions", [])),
                        "cv": user.get("cv", "#")
                    })
        return jsonify(matched_users)
    except Exception as e:
        print(f"Error in get_users: {e}")
        return jsonify({"error": str(e)}), 500

from datetime import datetime

@app.route('/health')
def health_check():
    try:
        # Check MongoDB connection
        mongo_status = "healthy" if collection is not None else "unhealthy"
        if collection is not None:
            # Try a simple query to test connection
            collection.find_one({})
        
        return {
            'status': 'healthy', 
            'timestamp': datetime.now().isoformat(),
            'mongodb': mongo_status
        }
    except Exception as e:
        return {
            'status': 'unhealthy', 
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
