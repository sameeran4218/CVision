import json
import os
import numpy as np
import pdfplumber
from dotenv import load_dotenv
import pinecone
from pinecone import *
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import cloudinary
from cloudinary.uploader import upload
from database import *
from llm import *

load_dotenv()

# initialize pinecone database
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
index_name = os.environ.get('PINECONE_INDEX_NAME')
index = pc.Index(index_name)

# initialize embeddings model + vector store
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_store = PineconeVectorStore(index=index, embedding=embeddings)

# function to store the company's ideal job description to vector data store
def storeVectorDB(job_desc:str,company:str,role:str,id:str)->None:
    document_1 = Document(
        page_content=job_desc,
        metadata={'company': company,'role':role},
    )
    vector_store.add_documents(documents=[document_1], ids=[id])


# function to extract text from the user uploaded cv
def extractUserCV(file_path)->str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# function to store the user uploaded cvs to Cloudinary
def storeCloudinary(file_path)->str:
    # Configure cloudinary
    cloudinary.config(
        cloud_name=os.environ.get('CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    # upload extracted text, along with metadata to cloudinary
    upload_result=cloudinary.uploader.upload_large(
        file_path,
        resource_type='raw',
        folder='CVEvaluator',
    )
    url=upload_result['secure_url']
    os.remove(file_path)
    return url

# function to get vector embedding and metadata from Pinecone based on ids
def fetchPineconeData(id:str):
    # fetch vectors by their ids
    result=index.fetch(ids=[id])
    vectors_data=result['vectors']
    # Each vector data contains 'id', 'values' (embedding), and 'metadata'
    for vid, vector_info in vectors_data.items():
        return vector_info.get('metadata')

# function to obtain an embedding vector of the text in user cv
def getEmbedding(user_text:str)->list:
    vector = embeddings.embed_query(user_text)
    return vector

# function to return a list of pinecone_ids that have similar vector embedding to user cv
def getSimilarVectors(user_vec)->list:
    results=index.query(
        vector=user_vec,
        top_k=3,
        include_values=True
    )
    id_list = [match['id'] for match in results['matches']]
    return id_list


# Full Workflow
def workFlow(file_path:str,username:str)->None:
    '''1. extract text from user's cv, store it on cloudinary
    2. get the embedding vector of user cv
    3. extract similar job descriptions from pinecone vector database using similarity of vectors
    4. for each id, get the metadata like company,role and job desc from pinecone
    5. Analyze the job desc against user cv using the Langchain + LLM(Groq)
    6. Finally store the company,role,username,usercv,cv score, suggestions,strengths and weakness to mongodb'''
    resume=extractUserCV(file_path)
    user_vec=getEmbedding(resume)
    ids=getSimilarVectors(user_vec)
    cv_url=storeCloudinary(file_path)
    for id in ids:
        ans=fetchPineconeData(id)
        company=ans['company']
        role=ans['role']
        job_desc=ans['text']
        user_details=json.loads(analyze_resume(job_desc,resume))
        user_details['name']=username
        user_details['cv']=cv_url
        addUserData(company,role,user_details)


