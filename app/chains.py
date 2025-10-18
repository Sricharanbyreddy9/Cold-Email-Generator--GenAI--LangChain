# app/chains.py
# End-to-end Chain class:
# - loads GROQ_API_KEY from .env
# - provides: extract_jobs(), write_mail(), find_skill_in_resume()

import os
import re
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.utils.json import parse_json_markdown, parse_partial_json

# --- load .env (do not hardcode keys) ---
ROOT = Path(__file__).resolve().parents[1]   # project root (one level above /app)
APP_DIR = Path(__file__).resolve().parent    # the /app folder

# load app/.env first, then root/.env (app wins)
load_dotenv(APP_DIR / ".env", override=True)
load_dotenv(ROOT / ".env",  override=True)

# --- tokenization helpers for skill extraction ---
TECH_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,}")
STOPWORDS = {
    "experience","experienced","expertise","expert","worked","work","knowledge",
    "with","in","on","of","for","and","the","a","an","as","at","to","using",
    "have","has","had","years","year","months","month","proficient","strong",
    "good","solid","hands-on","familiar","background","skill","skills"
}


class Chain:
    def __init__(self, model: str = "llama-3.3-70b-versatile", temperature: float = 0.2):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not found. Add it to .env (either app/.env or project .env) and restart the terminal."
            )
        self.llm = ChatGroq(model=model, temperature=temperature, groq_api_key=api_key)

    # ---------------------------------------------------------------------
    # 1) EXTRACT JOBS  ->  JSON list of postings from scraped careers text
    # ---------------------------------------------------------------------
    def extract_jobs(self, cleaned_text: str) -> List[Dict[str, Any]]:
        """
        Input: raw/scraped careers page text (already cleaned by you).
        Output: list[dict] of jobs with fields (title, location, skills, etc.).
        """
        prompt_extract = PromptTemplate.from_template(
            """
### SCRAPED TEXT FROM WEBSITE:
{page_data}

### INSTRUCTION:
The scraped text is from a careers page. Extract *every* distinct job posting and return **ONLY valid JSON**.
Use this schema (fields may be null if missing):
[
  {{
    "title": string,
    "location": string|null,
    "employment_type": string|null,
    "team": string|null,
    "skills": string[],          // dedupe, lower-case where sensible
    "description": string,       // concise 1–3 sentences from the posting
    "apply_url": string|null,    // canonical link if present
    "company": string|null
  }}
]
No prose, no markdown fences, no comments. Output pure JSON only.

### VALID JSON (NO PREAMBLE):
"""
        )

        res = (prompt_extract | self.llm).invoke({"page_data": cleaned_text})
        text = getattr(res, "content", str(res))

        # robust JSON parsing (JSON, ```json blocks, lenient)
        parser = JsonOutputParser()
        try:
            jobs = parser.parse(text)
        except OutputParserException:
            try:
                jobs = parse_json_markdown(text)
            except Exception:
                jobs = parse_partial_json(text)

        if isinstance(jobs, dict):
            jobs = jobs.get("jobs") or jobs.get("postings") or jobs.get("data") or []
        if not isinstance(jobs, list):
            return []

        # normalize + dedupe
        out: List[Dict[str, Any]] = []
        seen = set()
        for j in jobs:
            if not isinstance(j, dict):
                continue
            title = (j.get("title") or "").strip()
            if not title:
                continue
            loc = (j.get("location") or "").strip()
            key = (title.lower(), loc.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "title": title,
                "location": loc or None,
                "employment_type": (j.get("employment_type") or "").strip() or None,
                "team": (j.get("team") or "").strip() or None,
                "skills": sorted({s.strip().lower() for s in (j.get("skills") or []) if isinstance(s, str) and s.strip()}),
                "description": (j.get("description") or "").strip(),
                "apply_url": (j.get("apply_url") or "").strip() or None,
                "company": (j.get("company") or "").strip() or None,
            })
        return out

    # ---------------------------------------------------------------------
    # 2) WRITE MAIL  ->  Letter-style cold email grounded in resume + JD
    # ---------------------------------------------------------------------
    def write_mail(
        self,
        job_description: str,
        resume_text: str,
        your_name: str = "Sri Charan Reddy",
        title: str = "Software Engineer (Full-Stack & GenAI/ML)",
        years_exp: int = 4,
        years_ai_ml: int = 2,
        link_candidates: Optional[Iterable[str]] = None,
        company_or_generic: Optional[str] = None,
    ) -> str:
        """
        Builds inputs (smart greeting, trimmed JD, best link) and returns the final email text.
        """
        # smart greeting from JD if not supplied
        if not company_or_generic:
            m = re.search(r"(?:at|@|for)\s+([A-Z][\w&.\- ]{2,60})", job_description)
            company = m.group(1).strip().rstrip(".,") if m else None
            company_or_generic = f"{company} Hiring Manager" if company else "Hiring Manager"

        jd_snippet = re.sub(r"\s+", " ", job_description).strip()[:2500]

        # choose one link (prefer GitHub for genai/llm/rag roles)
        link_list = ""
        if link_candidates:
            if re.search(r"\brag\b|\bllm\b|\bgenai\b|\bchatbot|\bvector", job_description, flags=re.IGNORECASE):
                gh = next((l for l in link_candidates if "github" in l.lower()), None)
                link_list = gh or next(iter(link_candidates))
            else:
                link_list = next(iter(link_candidates))

        prompt_email = PromptTemplate.from_template(
            """
Write a tailored, letter-style cold email that a busy hiring manager will want to read—human, specific, and grounded ONLY in the resume below and the job description.
Length: 160–220 words.

Must follow this structure:
- Greeting: “Dear {company_or_generic},”
- Paragraph 1 (intro): 1–2 sentences introducing **{your_name}**, a **{title}** with **{years_exp}+ years** in production software and **{years_ai_ml}+ years** in AI/ML & GenAI.
- Paragraph 2 (capabilities aligned to JD): map JD needs (stack/domain/KPIs) to strengths:
  • Full-stack delivery (React/Next.js, Node/Python/Java, REST/GraphQL, PostgreSQL/MySQL), CI/CD (Docker, Kubernetes, GitHub Actions), reliability/observability.
  • GenAI with real impact (RAG over PDFs/knowledge, evaluations/guardrails, latency & cost tuning) using LangChain, OpenAI/Groq, Chroma/FAISS.
  Use resume-grounded outcomes; avoid buzzwords.
- Paragraph 3 (proof & CTA): include at least one concrete, resume-grounded result (latency, uptime, users, cost). Include ONE relevant link naturally from: {link_list}. Propose a 15-minute chat and name a realistic 30-day contribution aligned to the JD.
- Sign-off: “Best regards,” + name on next line.

Style constraints:
- No subject line. No headings. No bullet lists. No clichés. No invented facts.
- Prefer verbs and outcomes over tool dumps. Keep it warm, confident, and precise.

### JOB DESCRIPTION
{job_description}

### RESUME
{resume_text}
"""
        )

        vars_email = {
            "company_or_generic": company_or_generic,
            "your_name": your_name,
            "title": title,
            "years_exp": years_exp,
            "years_ai_ml": years_ai_ml,
            "link_list": link_list,
            "job_description": jd_snippet,
            "resume_text": resume_text,
        }
        return (prompt_email | self.llm).invoke(vars_email).content

    # ---------------------------------------------------------------------
    # 3) FIND SKILL IN RESUME  ->  detect skill tokens & optional Chroma link
    # ---------------------------------------------------------------------
    def find_skill_in_resume(
        self,
        sentence: str,
        resume_text: str,
        collection=None,                  # chromadb.Collection if you have one
        top_k: int = 1
    ) -> List[Dict[str, Optional[str]]]:
        """
        From a sentence (e.g., 'experience in Java'), return skill tokens present in
        the resume and, if a Chroma collection is provided, a related link.
        """
        tokens = TECH_TOKEN_RE.findall(sentence.lower())

        cleaned = []
        for t in tokens:
            t = t.strip(".-")
            if not t or t in STOPWORDS:
                continue
            cleaned.append(t)

        def in_resume(tok: str) -> bool:
            return re.search(rf"\b{re.escape(tok)}\b", resume_text, flags=re.IGNORECASE) is not None

        candidates = [t for t in cleaned if in_resume(t)]

        seen, ordered = set(), []
        for t in sorted(candidates, key=len, reverse=True):
            if t not in seen:
                seen.add(t)
                ordered.append(t)

        matches: List[Dict[str, Optional[str]]] = []
        for tok in ordered:
            link = None
            if collection is not None:
                res = collection.get(where_document={"$contains": tok}, include=["metadatas"])
                if res.get("ids"):
                    link = res["metadatas"][0].get("link")
            matches.append({"skill": tok, "link": link})
            if len(matches) >= top_k:
                break
        return matches


# ---- optional sanity check when running the file directly ----
if __name__ == "__main__":
    print("[dotenv] app/.env exists:", (APP_DIR / ".env").exists())
    print("[dotenv] root/.env exists:", (ROOT / ".env").exists())
    print("[dotenv] GROQ_API_KEY present?:", bool(os.getenv("GROQ_API_KEY")))
    c = Chain()
    jd = "Hiring Software Engineer for GenAI at Acme. Experience in React, Node, Python, Docker, Kubernetes; RAG/LLM a plus."
    resume = "Sri Charan Reddy — Full-stack & GenAI. React/Next.js, Node, Python, Java, Docker, K8s, AWS. Built RAG with LangChain/OpenAI/Chroma; improved latency & cost."
    print(c.write_mail(jd, resume, link_candidates=[
        "https://sricharanbyreddy.online/", "https://github.com/Sricharanbyreddy9"
    ]))
