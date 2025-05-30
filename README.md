# 🔍 CVision - AI Powered Resume Analyzer Platform

[![YouTube Demo](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/g1Y-4byQIcc)

CVision revolutionizes hiring with LLM powered cv analysis via Langchain which allows recruiters to get smart insights into candidate's resume and and cut down time.

![CVision Dashboard](https://github.com/user-attachments/assets/1137b117-1b05-4882-83b4-6c9223655c64)

---

## 🌟 Key Features

### For Job Seekers
- **AI Resume Report Card** - Scores your resume on ATS compatibility
- **Skill Gap Analysis** - Identifies missing skills for target roles
- **Personalized Suggestions** - Actionable improvement tips

### For Recruiters
- **Smart Candidate Ranking** - AI-driven fit scoring (1-100)
- **Comparative Analysis** - Personalized candidate evaluation based on strengths and weakness for each company and job.
- **Cloud-Based CV Parsing** - Instant insights without downloads

---

## 🛠️ Tech Stack

### Core Components
| Component | Technology |
|-----------|------------|
| Frontend |Flask|
| Resume Parser | LangChain + LLMs (Groq) |
| Vector Database | Pinecone |
| File Storage | Cloudinary |
| Database | MongoDB |

### AI Modules
- **Resume Analyzer** (LangChain + LLM (Groq))
- **Job-CV Matcher** (Pinecone similarity search)
- **Suggestion Generator** (LangChain + LLM (Groq))

---

## 🏗️ System Architecture

```mermaid
graph TD
    A[Candidate Uploads CV] --> B[Cloudinary Storage]
    B --> C[LangChain Processing]
    C --> D[Generate Embeddings]
    D --> E[Pinecone Indexing]
    F[Recruiter Posts Job] --> G[Job Description Embedding]
    E --> H[Similarity Matching]
    G --> H
    H --> I[LLM Analysis]
    I --> J[Fit Score + Insights]
    J --> K[MongoDB Storage]
    K --> L[Recruiter Dashboard]

