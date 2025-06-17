import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

load_dotenv()

# Step 1: Setup Groq LLM with error handling
try:
    llm = ChatGroq(model_name="llama3-70b-8192", api_key=os.getenv('GROQ_API_KEY'))
    print("Groq LLM initialized successfully")
except Exception as e:
    print(f"Error initializing Groq LLM: {e}")
    llm = None

# Step 2: Prompt Templates

system_prompt = "You are a Resume Analyzer LLM who compares resumes to job descriptions and returns a structured JSON analysis. Do not repeat input text."

few_shot_examples = """### Example 1
Job Description:
Software Engineer with 3+ years experience in JavaScript, React, and backend development using Node.js. Familiarity with AWS and CI/CD pipelines preferred.

Candidate Resume:
Jane Smith
- 4 years experience building web apps with React and Node.js
- Experienced in AWS services including EC2 and S3
- Familiar with Docker and Jenkins for CI/CD automation
- Strong communication and teamwork skills

Output:
{{
  "Fit Score": 92,
  "Strengths": [
    "4 years of React and Node.js experience",
    "Hands-on experience with AWS EC2 and S3",
    "Knowledge of Docker and Jenkins for CI/CD",
    "Strong communication and teamwork"
  ],
  "Weaknesses": [
    "No mention of database technologies",
    "No explicit mention of testing or debugging skills"
  ],
  "Suggestions": [
    "Add experience with database systems like SQL or NoSQL",
    "Highlight testing and debugging experience"
  ]
}}
---
"""

# Step 3: Chain Construction

def analyze_resume(job_desc: str, resume: str):
    if llm is None:
        print("LLM not available")
        return '{"Fit Score": 0, "Strengths": [], "Weaknesses": ["LLM service unavailable"], "Suggestions": ["Please try again later"]}'
    
    try:
        user_prompt = """### New Analysis Task

Job Description:
\"\"\"{job_description}\"\"\"

Candidate Resume:
\"\"\"{candidate_resume}\"\"\"

Output only in JSON format with the following keys:
- "Fit Score"
- "Strengths"
- "Weaknesses"
- "Suggestions"

OUTPUT ONLY JSON. DO NOT OUTPUT ANYTHING ELSE !!!!
"""

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template(few_shot_examples + user_prompt)
        ])

        chain = prompt | llm | StrOutputParser()

        result = chain.invoke({
            "job_description": job_desc,
            "candidate_resume": resume
        })

        return result
    except Exception as e:
        print(f"Error in analyze_resume: {e}")
        return '{"Fit Score": 0, "Strengths": [], "Weaknesses": ["Analysis failed"], "Suggestions": ["Please try again later"]}'

system_prompt_2 = """You are a helpful assistant who summarizes the suggestions provided to a user's CV in a concise yet descriptive way. DO NOT START WITH Here is a concise and descriptive summary of the suggestions:. START DIRECTLY LISTING OUT SUGGESTIONS."""

few_shot_examples_2 = """### Example 1
Job Description:
Software Engineer with 3+ years experience in JavaScript, React, and backend development using Node.js. Familiarity with AWS and CI/CD pipelines preferred.

Candidate Resume:
Jane Smith
- 4 years experience building web apps with React and Node.js
- Experienced in AWS services including EC2 and S3
- Familiar with Docker and Jenkins for CI/CD automation
- Strong communication and teamwork skills

Output: "Add experience with database systems like SQL or NoSQL",
    "Highlight testing and debugging experience" """

def summarize_suggestions(all_suggestions):
    if not all_suggestions:
        return 'No suggestions found for this user'
    
    if llm is None:
        print("LLM not available for summarization")
        return 'LLM service unavailable for summarization'
    
    try:
        user_prompt_2 = """ Please summarize the following suggestions \"\"\"{total_suggestions}\"\"\" """
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt_2),
            HumanMessagePromptTemplate.from_template(few_shot_examples_2 + user_prompt_2)
        ])
        chain = prompt | llm | StrOutputParser()

        result = chain.invoke({
            'total_suggestions': all_suggestions
        })

        return result
    except Exception as e:
        print(f"Error in summarize_suggestions: {e}")
        return f'Error summarizing suggestions: {str(e)}'
