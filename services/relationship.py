"""
Relationship Engine — uses Google Gemini Flash (with clean heuristic fallbacks) to identify connections
between documents and build an uncluttered knowledge graph (nodes + edges).
"""
import json
import os
import re
from typing import List, Dict
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

CANDIDATE_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]

SYSTEM_PROMPT = """You are an AI that maps relationships between a student's documents.
Given a list of documents (with id, category, title, skills), identify a few clear, non-redundant connections.

Return ONLY valid JSON in this exact format:
{"relationships": [
  {"source_id": <int>, "target_id": <int>, "relationship_type": "<string>", "description": "<string>"},
  ...
]}

Relationship types:
- "Skill → Project"
- "Project → Internship"
- "Certificate → Skill"
- "Academic → Project"
- "Resume → Internship"

Rules:
- Keep connections minimal and clean (maximum 1 or 2 relationships per document)
- Do not create a dense web of overlapping lines
- source_id and target_id must be integers from the list below
- Do not relate a document to itself"""


def _heuristic_relationships(docs: List[Dict]) -> List[Dict]:
    """
    Fallback graph builder: creates a clean, uncluttered set of connections
    (max 1-2 edges per node) based on category links, shared skills, or portfolio chain.
    """
    relationships = []
    seen_pairs = set()
    node_degree = {d["id"]: 0 for d in docs}

    def add_rel(src, tgt, rel_type, desc):
        if node_degree[src] >= 2 or node_degree[tgt] >= 2:
            return False
        pair = (min(src, tgt), max(src, tgt))
        if pair not in seen_pairs and src != tgt:
            seen_pairs.add(pair)
            node_degree[src] += 1
            node_degree[tgt] += 1
            relationships.append({
                "source_doc_id": src,
                "target_doc_id": tgt,
                "relationship_type": rel_type,
                "description": desc,
            })
            return True
        return False

    n = len(docs)
    # 1. Resume -> Project / Certificate / Academic links
    for d1 in docs:
        if d1.get("category") == "Resume":
            for d2 in docs:
                if d2["id"] != d1["id"] and d2.get("category") in ["Project", "Certificate", "Academic", "Internship"]:
                    add_rel(d1["id"], d2["id"], f"Resume → {d2.get('category')}", "Referenced in career portfolio")

    # 2. Shared Skills (only if degree < 2)
    for i in range(n):
        d1 = docs[i]
        s1 = set(d1.get("skills") or [])
        if not s1 or node_degree[d1["id"]] >= 2:
            continue
        for j in range(i + 1, n):
            d2 = docs[j]
            s2 = set(d2.get("skills") or [])
            common = s1.intersection(s2)
            if common:
                skill_name = list(common)[0]
                add_rel(d1["id"], d2["id"], f"Shared Skill ({skill_name})", f"Both use {skill_name}")

    # 3. Simple chain fallback if degree < 1
    for i in range(n - 1):
        d1, d2 = docs[i], docs[i + 1]
        if node_degree[d1["id"]] < 1 or node_degree[d2["id"]] < 1:
            add_rel(d1["id"], d2["id"], "Portfolio Link", "Connected entries")

    return relationships


def build_relationships(docs: List[Dict]) -> List[Dict]:
    """
    Analyze user documents and build an uncluttered connection graph.
    """
    if len(docs) < 2:
        return []

    doc_summaries = []
    for d in docs[:30]:
        skills_str = ", ".join(d.get("skills") or []) or "none"
        doc_summaries.append(
            f"ID={d['id']} | {d['category']} | \"{d['title']}\" | Skills: {skills_str}"
        )

    prompt = f"{SYSTEM_PROMPT}\n\nDocuments:\n" + "\n".join(doc_summaries)

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
            print(f"[Relationship] Model {m} failed: {e}")
            continue

    if not raw:
        return _heuristic_relationships(docs)

    try:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                return _heuristic_relationships(docs)
            data = json.loads(match.group())

        raw_rels = data.get("relationships", [])
        valid_ids = {d["id"] for d in docs}
        validated = []
        node_degree = {d["id"]: 0 for d in docs}

        for r in raw_rels:
            try:
                src = int(r.get("source_id"))
                tgt = int(r.get("target_id"))
            except (TypeError, ValueError):
                continue

            if src in valid_ids and tgt in valid_ids and src != tgt:
                if node_degree[src] < 2 and node_degree[tgt] < 2:
                    node_degree[src] += 1
                    node_degree[tgt] += 1
                    validated.append({
                        "source_doc_id": src,
                        "target_doc_id": tgt,
                        "relationship_type": str(r.get("relationship_type", "Related"))[:100],
                        "description": str(r.get("description", ""))[:250],
                    })

        if not validated:
            return _heuristic_relationships(docs)

        return validated

    except Exception:
        return _heuristic_relationships(docs)
