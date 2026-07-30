# 🧠 MemoryVerse AI '26

> **AI-powered Digital Identity System** — Transform scattered certificates, resumes, projects, and experiences into an intelligent, searchable knowledge repository.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Google-Gemini%201.5%20Flash-4285F4?logo=google)](https://aistudio.google.com)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-orange)](https://chromadb.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org)

---

## 🎯 The Problem

Students accumulate certificates, resumes, internship letters, project reports, and achievements across folders, emails, and cloud drives. As years pass, this valuable data becomes impossible to find or connect.

**MemoryVerse AI solves this.** Upload once → understand everything.

---

## ✨ Features

| Module | Description |
|---|---|
| 🤖 **AI Data Ingestion** | Upload PDF, DOCX, TXT — AI extracts and understands the content |
| 🗂️ **Intelligent Categorization** | GPT-4o-mini auto-classifies into Certificate, Project, Internship, Academic, Achievement, Resume |
| 🕸️ **Relationship Engine** | Discovers connections: Skill → Project → Internship → Career |
| 🗓️ **Journey Timeline** | Visual chronological view of your growth |
| 🔍 **Smart Retrieval (RAG)** | Ask in plain English: *"Show all my Python certificates"* |
| 💬 **AI Chat Assistant** | Conversational Q&A over your own documents |

---

## 🔐 Security Architecture

Security is built into every layer since your documents are your identity:

| Layer | Implementation |
|---|---|
| **Authentication** | JWT (HS256) — all endpoints require valid Bearer token |
| **Passwords** | bcrypt hashing — plaintext never stored |
| **API Key** | `GEMINI_API_KEY` stored in `.env` — never sent to frontend |
| **Data Isolation** | Every DB query scoped by `user_id` — no cross-user access |
| **File Storage** | `uploads/{user_id}/` — isolated per user |
| **File Validation** | Extension whitelist (.pdf, .docx, .txt), 10MB limit |
| **Path Traversal** | werkzeug `secure_filename` + path containment check |
| **Rate Limiting** | 10 uploads/min, 10 auth/min, 30 searches/min |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, XSS-Protection |
| **CORS** | Strict origin allow-list — no wildcard |
| **Audit Logging** | Every upload/download/delete/search logged |

---

## 🏗️ Architecture

```
Frontend (HTML/CSS/JS)
    │
    ▼ REST API (JWT Bearer)
FastAPI Backend
    ├── Auth (JWT + bcrypt)
    ├── Upload Pipeline → Extract → Categorize → Embed
    ├── Semantic Search (ChromaDB + OpenAI Embeddings)
    ├── RAG Chat (GPT-4o-mini + context retrieval)
    ├── Relationship Engine (GPT knowledge graph)
    └── Timeline API
    │
    ├── SQLite (metadata, users, relationships, audit logs)
    └── ChromaDB (per-user vector collections)
```

---

## 🚀 Quick Start

### 1. Clone & setup
```bash
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

### 3. Run
```bash
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — register, upload documents, and explore!

API docs at **http://localhost:8000/api/docs**

---

## 📁 Project Structure

```
memoryverse/
├── main.py                  # FastAPI app entry point
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
│   ├── categorizer.py      # GPT-4o-mini classification
│   ├── embedder.py         # ChromaDB + OpenAI embeddings
│   ├── relationship.py     # Knowledge graph builder
│   └── retriever.py        # RAG pipeline
├── routes/
│   ├── auth.py             # /api/auth/* (register, login, me)
│   ├── upload.py           # /api/upload
│   ├── documents.py        # /api/documents/* (CRUD + download)
│   ├── search.py           # /api/search, /api/chat
│   ├── timeline.py         # /api/timeline
│   └── graph.py            # /api/graph/*
├── uploads/                # Original files (user-isolated)
├── chroma_db/              # Vector store (local, persistent)
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## 🤖 AI/ML Techniques Used

- **OpenAI GPT-4o-mini** — Document categorization (structured JSON output), RAG synthesis, relationship mapping
- **OpenAI text-embedding-3-small** — Semantic embeddings for all documents
- **ChromaDB** — Local vector database with per-user isolated collections, cosine similarity search
- **RAG (Retrieval-Augmented Generation)** — Retrieve top-5 relevant chunks → GPT synthesizes grounded answer
- **Knowledge Graph** — Force-directed graph visualization with GPT-identified relationships
- **NLP** — Entity extraction (skills, organizations, dates) from raw document text

---

## 📊 API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register new account |
| POST | `/api/auth/login` | No | Login, get JWT |
| GET | `/api/auth/me` | Yes | Current user profile |
| POST | `/api/upload` | Yes | Upload document (PDF/DOCX/TXT) |
| GET | `/api/documents` | Yes | List all user documents |
| GET | `/api/documents/{id}/file` | Yes | Download original file |
| DELETE | `/api/documents/{id}` | Yes | Delete document |
| POST | `/api/search` | Yes | Semantic search + RAG answer |
| POST | `/api/chat` | Yes | Conversational RAG chat |
| GET | `/api/timeline` | Yes | Journey timeline data |
| GET | `/api/graph` | Yes | Knowledge graph nodes + edges |
| POST | `/api/graph/rebuild` | Yes | Rebuild AI relationships |

---

## 🎯 Evaluation Alignment

| Criterion | Implementation |
|---|---|
| AI Organization (40%) | GPT-4o-mini auto-categorizes every upload into 6 categories with skill extraction |
| AI/ML Techniques (25%) | Gemini embeddings (text-embedding-004), ChromaDB vector DB, RAG pipeline, Gemini Flash knowledge graph, NLP entity extraction |
| Innovation & UX (20%) | Force-directed knowledge graph, animated timeline, conversational search, glassmorphism UI |
| Architecture Clarity (15%) | This README + modular code structure + full security documentation |

---

## 👤 Author

Built for MemoryVerse AI '26 Challenge.
