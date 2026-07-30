# 📋 MemoryVerse Portfolio — Reviewer's Note

> **Project**: MemoryVerse Portfolio  
> **Author**: Krish Kumar  
> **Repository**: [github.com/KrishKumar3k/memoryverse](https://github.com/KrishKumar3k/memoryverse)  
> **Live URL**: [memoryverse-two.vercel.app](https://memoryverse-two.vercel.app)  

---

## 🎯 What is MemoryVerse?

MemoryVerse is an **AI-powered Executive Digital Identity & Knowledge Management Platform** built for professionals, students, and executives who want to intelligently organize, search, and visualize their academic and professional documents.

Instead of manually sorting certificates, project reports, and resumes — users upload their files and let Gemini AI automatically extract metadata, classify documents, identify skill connections, and build a living knowledge graph of their professional journey.

---

## 🧠 Core Features

| Feature | Description |
|---|---|
| 🔐 **Secure Authentication** | JWT-based login/registration with bcrypt password hashing |
| 📄 **Document Ingestion** | Upload PDF, DOCX, TXT — AI auto-extracts title, summary, skills, date, org |
| 🤖 **AI Metadata Extraction** | Google Gemini API reads and classifies each document |
| 🕸️ **Knowledge Network Graph** | Interactive canvas visualization of document relationships |
| 🔗 **Manual Graph Connections** | Users can create & delete custom connections between documents |
| 🔍 **Intelligent Search & Chat** | Semantic RAG similarity search powered by Gemini embeddings + cosine similarity |
| 📅 **Career Timeline** | Auto-generated chronological timeline from uploaded documents |
| 🌗 **Dark / Light Mode** | Full theme toggle with persistent state |
| 🔒 **Protected Admin API Docs** | `/api/docs` gated behind HTTP Basic Authentication |
| 👑 **Admin User Count** | Admin endpoint to view total registered users |
| 🔈 **Audit Logging** | Every upload, search, and document access is logged per user |

---

## 🛠️ Technology Stack

### Backend
| Technology | Version | Role |
|---|---|---|
| **Python** | 3.11+ | Core language |
| **FastAPI** | 0.115.6 | REST API framework with async support |
| **Uvicorn** | 0.34.0 | ASGI server |
| **Pydantic v2** | 2.10.4 | Data validation and schemas |
| **SQLAlchemy** | 2.0.36 | ORM for database models |
| **SQLite** | Built-in | Lightweight relational database |
| **python-jose** | 3.3.0 | JWT token creation & validation |
| **passlib + bcrypt** | 1.7.4 / 4.2.1 | Secure password hashing |
| **python-multipart** | 0.0.20 | File upload form handling |
| **python-dotenv** | 1.0.1 | Environment variable management |
| **Werkzeug** | 3.1.3 | Secure filename sanitization |

### AI / Machine Learning
| Technology | Version | Role |
|---|---|---|
| **Google Gemini AI** | `gemini-flash-latest` | Document content extraction, classification, & chat RAG |
| **Gemini Embedding Model** | `models/gemini-embedding-001` | 768-dim embeddings for semantic search |
| **Pure-Python Cosine Similarity** | Custom | Vector search without heavy dependencies |
| **pypdf** | 5.1.0 | Lightweight PDF text extraction |
| **python-docx** | 1.1.2 | DOCX text extraction |

### Frontend
| Technology | Role |
|---|---|
| **Vanilla HTML5** | Semantic page structure |
| **Vanilla CSS3** | Custom design system with CSS variables, dark/light themes |
| **Vanilla JavaScript (ES6+)** | All interactivity, API calls, DOM manipulation |
| **HTML5 Canvas API** | Knowledge network graph rendering (nodes + edges) |
| **Google Fonts (Inter)** | Premium typography |
| **Fetch API** | Async REST API communication |

### DevOps & Deployment
| Technology | Role |
|---|---|
| **Vercel** | Serverless deployment via `@vercel/python` |
| **GitHub** | Source control + CI/CD trigger for Vercel auto-deploys |
| **`.env` + `.env.example`** | Secrets management — credentials never committed |

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────┐
│                  Browser / Client                   │
│        HTML + CSS + Vanilla JS + Canvas API         │
└───────────────────────┬────────────────────────────┘
                        │ HTTP REST (Fetch API)
┌───────────────────────▼────────────────────────────┐
│              FastAPI Backend (Python)               │
│                                                     │
│  /auth    /upload    /search    /graph   /timeline  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │          Google Gemini AI Layer              │  │
│  │  gemini-flash-latest + gemini-embedding-001  │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │     SQLite Database (SQLAlchemy ORM)         │  │
│  │  Users · Documents · Relationships · Logs    │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        │
             ┌──────────▼──────────┐
             │   Vercel Serverless  │
             │   (api/index.py)     │
             └─────────────────────┘
```

---

## 🔒 Security Highlights

- **Passwords** stored only as `bcrypt` hashes — never plaintext
- **JWT tokens** expire after configurable TTL, verified on every protected route
- **Admin API docs** (`/api/docs`) require HTTP Basic credentials — browsers show a native login prompt
- **File uploads** sanitized via `werkzeug.secure_filename` + UUID prefix to prevent path traversal
- **`.env` is gitignored** — no API keys or credentials are ever committed to GitHub
- **CORS** configurable via `ALLOWED_ORIGINS` environment variable
- **Security headers** injected by custom `middleware/security.py`
- **Audit logs** record every action with timestamp and IP address

---

## 💡 Notable Design Decisions

* **No Heavy Vector DB**: ChromaDB was originally planned but replaced with pure-Python cosine similarity over SQLite JSON columns. This cut the bundle from **508 MB → ~20 MB**, fitting within Vercel's 500 MB serverless limit.
* **Serverless-aware SQLite**: On Vercel, the database is stored at `/tmp/memoryverse.db`. WAL journal mode is conditionally skipped on Vercel to avoid `/tmp` file locking errors.
* **No Frontend Framework**: The entire UI is Vanilla HTML/CSS/JS with a canvas-based graph — no React, Vue, or Angular. This keeps the bundle lean with zero build steps while delivering a fully premium dark/light-mode experience.

---

## 🌐 Environment Variables Required

```env
# JWT Auth
SECRET_KEY=your_jwt_secret_here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Google Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# Admin credentials (for /api/docs access)
ADMIN_DOCS_USER=krish
ADMIN_DOCS_PASS=your_admin_password

# Optional
ALLOWED_ORIGINS=https://memoryverse-two.vercel.app
UPLOAD_DIR=/tmp/uploads
```

---

*MemoryVerse Portfolio — Built with ❤️ by Krish Kumar*
