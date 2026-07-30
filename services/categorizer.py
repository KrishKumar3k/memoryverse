"""
AI categorization service — uses Google Gemini Flash to classify and extract
structured metadata from document text and filename. Includes smart heuristic fallback.
"""
import json
import os
import re
from pathlib import Path
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

CANDIDATE_MODELS = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-2.0-flash"]
CATEGORIES = ["Certificate", "Resume", "Project", "Internship", "Achievement", "Academic", "Other"]

SYSTEM_PROMPT = """You are an expert document classifier for a student portfolio system.
Analyze the document filename and text content below and extract structured metadata. Return ONLY valid JSON.

CATEGORY RULES (pick the BEST match):
- "Certificate"  → any certificate, course completion, training credential, online course (Coursera, Udemy, NPTEL, etc.)
- "Resume"       → CV, resume, bio-data, curriculum vitae
- "Project"      → project report, project description, capstone, Kaggle writeup, lab project, source code writeup
- "Internship"   → internship offer letter, internship completion letter, work experience letter
- "Achievement"  → award, honor, rank, scholarship, competition result
- "Academic"     → marksheet, transcript, degree, admit card, semester result, course notes/basics
- "Other"        → only if NONE of the above fit at all

Return this exact JSON structure:
{
  "category": "<one of the 7 categories above>",
  "title": "<descriptive title, keep close to original filename if specific>",
  "summary": "<2-3 sentence summary of this document>",
  "skills": ["<skill1>", "<skill2>", ...],
  "date": "<YYYY-MM or YYYY if a date is visible in the document, else null>",
  "organization": "<issuing org, university, or company name if visible, else null>"
}

Be decisive — always pick the most specific category based on filename and text."""


def _filename_heuristics(filename: str) -> dict:
    """Fallback rule-based categorization based on file name keywords."""
    clean_name = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    lower = filename.lower()

    category = "Other"
    if any(k in lower for k in ["cv", "resume", "biodata", "curriculum"]):
        category = "Resume"
        skills = ["Resume Formatting", "Career Profile"]
    elif any(k in lower for k in ["cert", "certificate", "coursera", "udemy", "nptel", "completion"]):
        category = "Certificate"
        skills = ["Certified Professional"]
    elif any(k in lower for k in ["project", "kaggle", "writeup", "capstone", "repo", "app", "model"]):
        category = "Project"
        skills = ["Project Development"]
    elif any(k in lower for k in ["intern", "internship", "offer", "stipend", "experience"]):
        category = "Internship"
        skills = ["Professional Experience"]
    elif any(k in lower for k in ["marksheet", "transcript", "academic", "basics", "notes", "python", "degree", "diploma", "semester"]):
        category = "Academic"
        skills = ["Academic Knowledge"]
    elif any(k in lower for k in ["award", "achievement", "rank", "winner", "medal"]):
        category = "Achievement"
        skills = ["Honors & Awards"]
    else:
        skills = []

    if "python" in lower:
        skills.append("Python")
    if "machine learning" in lower or "ml" in lower:
        skills.append("Machine Learning")
    if "sql" in lower:
        skills.append("SQL")
    if "react" in lower or "js" in lower:
        skills.append("Web Development")

    return {
        "category": category,
        "title": clean_name or "Document",
        "summary": f"Document titled {clean_name}",
        "skills": list(set(skills)),
        "date": None,
        "organization": None,
    }


def categorize_document(text: str, filename: str = "") -> dict:
    """
    Sends document text & filename to Gemini Flash and returns structured metadata.
    Falls back to filename heuristics if Gemini call fails.
    """
    fallback = _filename_heuristics(filename) if filename else _default_metadata()
    prompt = f"{SYSTEM_PROMPT}\n\nFilename: {filename}\n\nDocument text snippet:\n\n{text[:5000]}"

    raw = None
    for m in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(
                model_name=m,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=800,
                ),
            )
            res = model.generate_content(prompt)
            if res.text:
                raw = res.text.strip()
                break
        except Exception as e:
            print(f"[Categorizer] Model {m} failed: {e}")
            continue

    if not raw:
        print("[Categorizer] All Gemini models failed or timed out. Using heuristic fallback.")
        return fallback

    try:
        data = json.loads(raw)
        return _validate_metadata(data, filename)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return _validate_metadata(data, filename)
            except Exception:
                pass

    return fallback


def _validate_metadata(data: dict, filename: str = "") -> dict:
    category = data.get("category", "")
    cat_map = {
        "certificate": "Certificate", "cert": "Certificate",
        "resume": "Resume", "cv": "Resume", "curriculum vitae": "Resume",
        "project": "Project", "internship": "Internship",
        "achievement": "Achievement", "award": "Achievement",
        "academic": "Academic", "other": "Other",
    }
    normalized = cat_map.get(str(category).lower().strip(), None)
    if normalized:
        category = normalized

    clean_filename = Path(filename).stem.replace("_", " ").strip() if filename else "Document"

    if category not in CATEGORIES or category == "Other":
        if filename:
            heur = _filename_heuristics(filename)
            if heur["category"] != "Other":
                category = heur["category"]
            if not data.get("skills"):
                data["skills"] = heur["skills"]

    title = str(data.get("title") or "").strip()
    if not title or title.lower() in ["untitled", "untitled document", "document"]:
        title = clean_filename

    return {
        "category": category if category in CATEGORIES else "Other",
        "title": title[:500],
        "summary": str(data.get("summary") or "")[:1000],
        "skills": [str(s) for s in data.get("skills", []) if s][:20],
        "date": str(data.get("date") or "")[:10] if data.get("date") else None,
        "organization": str(data.get("organization") or "")[:500] if data.get("organization") else None,
    }


def _default_metadata() -> dict:
    return {
        "category": "Other",
        "title": "Document",
        "summary": "",
        "skills": [],
        "date": None,
        "organization": None,
    }
