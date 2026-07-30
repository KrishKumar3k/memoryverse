# 🧠 MemoryVerse AI '26

> **AI-powered Digital Identity System** — Transform scattered certificates, resumes, projects, and experiences into an intelligent, searchable knowledge repository powered by Google Gemini AI.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Google-Gemini%20Flash%20%26%20Embeddings-4285F4?logo=google)](https://aistudio.google.com)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-orange)](https://chromadb.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org)

---

## 🎯 The Problem

Students and professionals accumulate certificates, resumes, internship letters, project reports, and achievements across folders, emails, and cloud drives. As years pass, this valuable data becomes impossible to find or connect.

**MemoryVerse AI solves this.** Upload once → understand everything.

---

## ✨ Features

| Module | Description |
|---|---|
| 🤖 **AI Data Ingestion** | Upload PDF, DOCX, TXT — Gemini AI extracts and understands document content |
| 🗂️ **Intelligent Categorization** | Gemini Auto-classifies into Certificate, Project, Internship, Academic, Achievement, Resume |
| 🕸️ **Relationship Engine** | Discovers connections: Skill → Project → Internship → Career |
| 🗓️ **Journey Timeline** | Visual chronological record of your verified growth |
| 🔍 **Smart Retrieval (RAG)** | Ask in plain English: *"Show all my Python certificates"* |
| 💬 **AI Chat Assistant** | Conversational Q&A grounded over your portfolio assets |
| ➕ **Manual Connections** | Create and manage custom document knowledge links manually |

---

## 🔐 Security Architecture

Security is built into every layer since your documents represent your identity:

| Layer | Implementation |
|---|---|
| **Authentication** | JWT (HS256) — all endpoints require valid Bearer token |
| **Passwords** | bcrypt hashing — plaintext never stored |
| **API Key** | `GEMINI_API_KEY` stored securely in `.env` — never sent to frontend |
| **Data Isolation** | Every DB query scoped by `user_id` — no cross-user access |
| **File Storage** | `uploads/{user_id}/` — isolated per user |
| **File Validation** | Extension whitelist (.pdf, .docx, .txt), 10MB limit |
| **Path Traversal** | werkzeug `secure_filename` + path containment check |
| **Rate Limiting** | 10 uploads/min, 10 auth/min, 30 searches/min |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, XSS-Protection |
| **Admin Protection** | Protected HTTP Basic Auth on `/api/docs` and `/api/redoc` |
| **CORS** | Strict origin allow-list |
| **Audit Logging** | Every upload/download/delete/search logged |

---

## 🏗️ Architecture

```
Frontend (HTML5 / Vanilla CSS / ES6 JavaScript)
    │
    ▼ REST API (JWT Bearer)
FastAPI Backend
    ├── Auth (JWT + bcrypt)
    ├── Upload Pipeline → Extract → Categorize → Embed
    ├── Semantic Search (ChromaDB + Gemini Embeddings)
    ├── RAG Chat (Gemini Flash + context retrieval)
    ├── Relationship Engine (Gemini knowledge graph)
    └── Timeline & Manual Graph APIs
    │
    ├── SQLite (metadata, users, relationships, audit logs)
    └── ChromaDB (per-user vector collections)
```

---

## 🚀 Quick Start

### 1. Clone & setup
```bash
git clone https://github.com/KrishKumar3k/memoryverse.git
cd memoryverse
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 2. Configure
```bash
copy .env.example .env
# Edit .env — set GEMINI_API_KEY and SECRET_KEY
```

**Get a FREE Gemini API key:** https://aistudio.google.com/apikey

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Run Locally
```bash
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — register, upload documents, and explore!

Admin API docs at **http://localhost:8000/api/docs**

---

## 📁 Project Structure

```
memoryverse/
├── main.py                  # FastAPI app entry point
├── vercel.json              # Vercel serverless deployment config
├── requirements.txt
├── .env.example
├── auth/
│   └── jwt_handler.py       # JWT creation, bcrypt, user dependency
├── database/
│   ├── db.py               # SQLAlchemy + SQLite setup
│   └── models.py           # User, Document, Relationship, AuditLog
├── middleware/
│   └── security.py         # Rate limiting, security headers
├── services/
│   ├── extractor.py        # PDF/DOCX/TXT text extraction
│   ├── categorizer.py      # Google Gemini document classification
│   ├── embedder.py         # ChromaDB + Google Gemini embeddings
│   ├── relationship.py     # Knowledge graph engine
│   └── retriever.py        # Gemini RAG pipeline
├── routes/
│   ├── auth.py             # /api/auth/* (register, login, user count)
│   ├── upload.py           # /api/upload
│   ├── documents.py        # /api/documents/* (CRUD + download)
│   ├── search.py           # /api/search, /api/chat
│   ├── timeline.py         # /api/timeline
│   └── graph.py            # /api/graph/* (get, rebuild, manual connections)
├── uploads/                # Original files (user-isolated)
├── chroma_db/              # Vector store (local, persistent)
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## 🤖 AI/ML Techniques Used

- **Google Gemini AI (gemini-flash-latest / gemini-3.6-flash)** — Document categorization, RAG synthesis, and relationship mapping
- **Google Gemini Embeddings (gemini-embedding-001)** — High-dimensional semantic embeddings for indexed portfolio assets
- **ChromaDB** — Vector database with per-user isolated collections and cosine similarity search
- **RAG (Retrieval-Augmented Generation)** — Retrieve relevant document chunks → Gemini Flash synthesizes grounded response
- **Knowledge Network** — Interactive force-directed canvas graph visualization with AI & manual relationship controls
- **NLP Entity Extraction** — Automated extraction of skills, organizations, and dates from raw document text

---

## 📊 API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register new account |
| POST | `/api/auth/login` | No | Login, get JWT |
| GET | `/api/auth/me` | Yes | Current user profile |
| GET | `/api/auth/admin/users-count` | Yes | System registered user statistics |
| POST | `/api/upload` | Yes | Upload document (PDF/DOCX/TXT) |
| GET | `/api/documents` | Yes | List all user documents |
| GET | `/api/documents/{id}/file` | Yes | Download original file |
| DELETE | `/api/documents/{id}` | Yes | Delete document |
| POST | `/api/search` | Yes | Semantic search + RAG answer |
| POST | `/api/chat` | Yes | Conversational RAG chat |
| GET | `/api/timeline` | Yes | Journey timeline data |
| GET | `/api/graph` | Yes | Knowledge graph nodes + edges |
| POST | `/api/graph/rebuild` | Yes | Rebuild AI relationships |
| POST | `/api/graph/relationship` | Yes | Create manual custom relationship connection |
| DELETE | `/api/graph/relationship/{src}/{tgt}` | Yes | Delete specific document connection |

---

## 👤 Author

Trademark by **KK** · Built for MemoryVerse AI Portfolio System.
