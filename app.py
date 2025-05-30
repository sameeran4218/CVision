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
from database import get_user_suggestions
from llm import summarize_suggestions
import uuid
# Import functions
from utilities import *

load_dotenv()

app = Flask(__name__)

# create secret key to restrict access to form
app.config['SECRET_KEY']=os.environ.get('FLASK_SECRET_KEY')
# intilize the uploads folder to upload CV's
app.config['UPLOADS_FOLDER'] = 'uploads'

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

        # 🔍 Get suggestions for this user (name-based match)
        suggestions = get_user_suggestions(userName)
        suggestion_summary = summarize_suggestions(suggestions)

    return render_template(
        'user.html',
        form=form,
        summary=suggestion_summary  # pass to template
    )

# async function to handle the complete workflow
def async_Workflow(file_path,userName):
    workFlow(file_path,userName)

# Recruiter's Page
@app.route('/recruiter', methods=['GET', 'POST'])
def recruiter():
    form = jobDescForm()
    companyName = jobRole = jobDesc = None
    if form.validate_on_submit():
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
    return render_template('recruiter.html',
                           companyName=companyName,
                           jobRole=jobRole,
                           jobDesc=jobDesc,
                           form=form)

# async function to pass data to vector store
def async_storeVectorDB(company:str,role:str,desc:str,id:str)->None:
    storeVectorDB(company=company,role=role,job_desc=desc,id=id)


# Connect to MongoDB
client = MongoClient(os.environ.get('MONGO_URI'), server_api=ServerApi('1'))
db = client["CVDataStorage"]
collection = db["user"]

@app.route("/")
def index():
    try:
        # Optional: you can still pass companies for fallback/initial load
        companies = collection.distinct("company")
        return render_template("dashboard.html", companies=companies)
    except Exception as e:
        # Fallback if MongoDB is down
        return render_template("dashboard.html", companies=[])

@app.route("/get_companies")
def get_companies():
    try:
        companies = collection.distinct("company")
        return jsonify(companies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_roles")
def get_roles():
    company = request.args.get("company")
    if not company:
        return jsonify([])

    try:
        doc = collection.find_one({"company": company})
        roles = [role['role'] for role in doc.get("roles", [])] if doc else []
        return jsonify(roles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_users")
def get_users():
    company = request.args.get("company")
    role = request.args.get("role")

    if not company or not role:
        return jsonify([])

    try:
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
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)