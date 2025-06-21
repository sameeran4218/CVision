import json
import os
import numpy as np
import pdfplumber
from dotenv import load_dotenv
import pinecone
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import cloudinary
from cloudinary.uploader import upload
from database import addUserData
from llm import analyze_resume

load_dotenv()

# Initialize Pinecone database with error handling
try:
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    index_name = os.environ.get('PINECONE_INDEX_NAME')
    index = pc.Index(index_name)
    print("Pinecone initialized successfully")
except Exception as e:
    print(f"Pinecone initialization failed: {e}")
    pc = None
    index = None

# Initialize embeddings model + vector store with error handling
try:
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    if index is not None:
        vector_store = PineconeVectorStore(index=index, embedding=embeddings)
    else:
        vector_store = None
    print("Embeddings initialized successfully")
except Exception as e:
    print(f"Embeddings initialization failed: {e}")
    embeddings = None
    vector_store = None

# Initialize Cloudinary with error handling
try:
    cloudinary.config(
        cloud_name=os.environ.get('CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    print("Cloudinary configured successfully")
except Exception as e:
    print(f"Cloudinary configuration failed: {e}")

# function to store the company's ideal job description to vector data store
def storeVectorDB(job_desc: str, company: str, role: str, id: str) -> None:
    if vector_store is None:
        print("Vector store not available")
        return
    
    try:
        document_1 = Document(
            page_content=job_desc,
            metadata={'company': company, 'role': role},
        )
        vector_store.add_documents(documents=[document_1], ids=[id])
        print(f"Job description stored in vector DB for {company} - {role}")
    except Exception as e:
        print(f"Error storing in vector DB: {e}")

# function to extract text from the user uploaded cv
def extractUserCV(file_path) -> str:
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting CV text: {e}")
        return ""

# function to store the user uploaded cvs to Cloudinary
def storeCloudinary(file_path) -> str:
    try:
        # upload extracted text, along with metadata to cloudinary
        upload_result = cloudinary.uploader.upload_large(
            file_path,
            resource_type='raw',
            folder='CVEvaluator',
        )
        url = upload_result['secure_url']
        
        # Clean up local file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        print(f"CV uploaded to Cloudinary: {url}")
        return url
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return ""

# function to get vector embedding and metadata from Pinecone based on ids
def fetchPineconeData(id: str):
    if index is None:
        print("Pinecone index not available")
        return None
    
    try:
        # fetch vectors by their ids
        result = index.fetch(ids=[id])
        vectors_data = result['vectors']
        # Each vector data contains 'id', 'values' (embedding), and 'metadata'
        for vid, vector_info in vectors_data.items():
            return vector_info.get('metadata')
    except Exception as e:
        print(f"Error fetching Pinecone data: {e}")
        return None

# function to obtain an embedding vector of the text in user cv
def getEmbedding(user_text: str) -> list:
    if embeddings is None:
        print("Embeddings not available")
        return []
    
    try:
        vector = embeddings.embed_query(user_text)
        return vector
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return []

# function to return a list of pinecone_ids that have similar vector embedding to user cv
def getSimilarVectors(user_vec) -> list:
    if index is None or not user_vec:
        print("Pinecone index or user vector not available")
        return []
    
    try:
        results = index.query(
            vector=user_vec,
            top_k=3,
            include_values=True
        )
        id_list = [match['id'] for match in results['matches']]
        return id_list
    except Exception as e:
        print(f"Error getting similar vectors: {e}")
        return []

# Full Workflow
def workFlow(file_path: str, username: str) -> None:

    
    try:
        print(f"Starting workflow for user: {username}")
        
        # Step 1: Extract text from CV
        resume = extractUserCV(file_path)
        if not resume:
            print("Failed to extract text from CV")
            return
        
        # Step 2: Get embedding vector
        user_vec = getEmbedding(resume)
        if not user_vec:
            print("Failed to get embedding vector")
            return
        
        # Step 3: Get similar vectors
        ids = getSimilarVectors(user_vec)
        if not ids:
            print("No similar job descriptions found")
            return
        
        # Step 4: Store CV in Cloudinary
        cv_url = storeCloudinary(file_path)
        if not cv_url:
            print("Failed to upload CV to Cloudinary")
            cv_url = "#"  # Fallback URL
        
        # Step 5: Process each matching job description
        for id in ids:
            try:
                ans = fetchPineconeData(id)
                if not ans:
                    continue
                
                company = ans.get('company', 'Unknown')
                role = ans.get('role', 'Unknown')
                job_desc = ans.get('text', '')
                
                # Step 6: Analyze resume against job description
                analysis_result = analyze_resume(job_desc, resume)
                user_details = json.loads(analysis_result)
                
                # Add user info
                user_details['name'] = username
                user_details['cv'] = cv_url
                
                # Step 7: Store in MongoDB
                addUserData(company, role, user_details)
                print(f"Analysis completed for {company} - {role}")
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error for job ID {id}: {e}")
                continue
            except Exception as e:
                print(f"Error processing job ID {id}: {e}")
                continue
        
        print(f"Workflow completed for user: {username}")
        
    except Exception as e:
        print(f"Error in workflow: {e}")
