# app/main.py
# Cold Email Generator — robust fetch + flexible skill mining + heuristic fallback
# Paste a job URL → extract posting(s) or build one heuristically → generate a resume-grounded email.
# Starts with EMPTY URL (you paste your own). Clean, professional UI.

from __future__ import annotations
import os, sys, re
from typing import Dict, Any, List, Set

import streamlit as st

# ----------------------------- ROBUST FETCHERS -----------------------------

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

def _fetch_langchain(url: str) -> str:
    try:
        try:
            from langchain_community.document_loaders import WebBaseLoader
        except ModuleNotFoundError:
            from langchain_community.document_loaders.web_base import WebBaseLoader
        loader = WebBaseLoader([url], requests_kwargs={"headers": _HEADERS})
        docs = loader.load()
        return "\n\n".join(d.page_content or "" for d in docs)
    except Exception:
        return ""

def _fetch_requests(url: str) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
        r = requests.get(url, headers=_HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript", "template"]):
            t.decompose()
        return soup.get_text(" ", strip=True)
    except Exception:
        return ""

def _fetch_cloudscraper(url: str) -> str:
    try:
        import cloudscraper
        from bs4 import BeautifulSoup
        s = cloudscraper.create_scraper()
        r = s.get(url, headers=_HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript", "template"]):
            t.decompose()
        return soup.get_text(" ", strip=True)
    except Exception:
        return ""

def _fetch_requests_html(url: str) -> str:
    try:
        from requests_html import HTMLSession
        sess = HTMLSession()
        r = sess.get(url, headers=_HEADERS, timeout=25)
        r.html.render(timeout=30, sleep=1)
        return (r.html.text or "").strip()
    except Exception:
        return ""

def fetch_job_text(url: str, allow_js: bool) -> str:
    for fn in (_fetch_langchain, _fetch_requests, _fetch_cloudscraper):
        txt = fn(url)
        if len(txt) > 800:
            return txt
    if allow_js:
        txt = _fetch_requests_html(url)
        if len(txt) > 800:
            return txt
    return ""


# ----------------------------- APP MODULES -----------------------------
from chains import Chain
from portfolio import Portfolio
from utils import clean_text

# ----------------------------- TERM MINING -----------------------------

TOKEN_PATT = r"[A-Za-z][A-Za-z0-9\+\#\.\-]{1,}"

def mine_terms(text: str) -> Set[str]:
    """Pull tech-like tokens (keeps C++, .NET, Next.js etc.)."""
    toks = {m.group(0).lower() for m in re.finditer(TOKEN_PATT, text or "")}
    return {t for t in toks if 2 <= len(t) <= 32}

def overlap_terms(jd_text: str, resume_text: str) -> List[str]:
    """Compute intersection of JD tokens and resume tokens (no fixed list)."""
    jd = mine_terms(jd_text)
    cv = mine_terms(resume_text)
    terms = sorted(jd & cv, key=len, reverse=True)
    STOP = {"and","the","with","using","for","from","into","data","team","role","work","experience","years"}
    return [t for t in terms if t not in STOP][:50]


# ----------------------------- UI & HELPERS -----------------------------

def style_ui():
    st.set_page_config(page_title="Cold Email Generator", page_icon="📧", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { max-width: 1160px; margin: 0 auto; }
        .subtle { color:#627083; font-size:0.95rem; }
        .pill { display:inline-block; padding:2px 10px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; }
        .stButton>button { border-radius:10px; height:42px; }
        textarea, .stTextInput>div>div>input { font-size:15px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("📧 Cold Email Generator")
    st.markdown("<p class='subtle'>Paste a job URL → extract a posting → generate a concise, resume-grounded email.</p>", unsafe_allow_html=True)

ROLE_WORDS = r"(engineer|developer|manager|lead|scientist|analyst|architect|specialist|intern|consultant)"
CITY_STATE = r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)*,\s?(?:[A-Z]{2}|[A-Z][a-z]+))"

def heuristic_job_from_text(text: str, url: str, resume_text: str, extra_terms: Set[str]) -> Dict[str, Any] | None:
    """Fallback posting with flexible skills (overlap + user extras)."""
    if not text.strip():
        return None

    # title
    title = None
    for line in text.splitlines():
        line = line.strip()
        if 4 < len(line) < 90 and re.search(ROLE_WORDS, line, flags=re.I):
            title = line
            break
    if not title:
        slug = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"[-_]+", " ", slug)
        slug = re.sub(r"\b(r-|job|careers?)\b", "", slug, flags=re.I).strip()
        title = slug.title()[:80] or "Job Opportunity"

    # location
    m_loc = re.search(CITY_STATE, text)
    location = m_loc.group(0) if m_loc else None

    # skill candidates:
    olap = set(overlap_terms(text, resume_text))                   # auto-jd ∩ resume
    present_extras = {t for t in (extra_terms or set())
                      if re.search(rf"\b{re.escape(t)}\b", text, flags=re.I)}

    skills = sorted(olap | present_extras)

    description = text[:1200].strip()

    return {
        "title": title,
        "location": location,
        "employment_type": None,
        "team": None,
        "skills": skills,
        "description": description,
        "apply_url": url,
        "company": None,
    }

def ensure_core(primary_link: str, extra_links_csv: str, rebuild: bool) -> tuple[Chain, Portfolio, List[str]]:
    if "chain" not in st.session_state:
        st.session_state.chain = Chain()
    resume_pdf = os.path.join("app", "resource", "Sri Charan Reddy Software_Engineer_Resume.pdf")
    if ("portfolio" not in st.session_state) or rebuild:
        st.session_state.portfolio = Portfolio(
            pdf_path=resume_pdf, link=primary_link, vector_dir="vectorstore",
            collection_name="portfolio", reset=rebuild
        )
    extras = [s.strip() for s in (extra_links_csv or "").split(",") if s.strip()]
    return st.session_state.chain, st.session_state.portfolio, [primary_link] + extras

def job_to_description(job: Dict[str, Any]) -> str:
    parts = [
        f"Title: {job.get('title','')}",
        f"Location: {job.get('location') or ''}",
        f"Type: {job.get('employment_type') or ''}",
        f"Team: {job.get('team') or ''}",
        f"Skills: {', '.join(job.get('skills', []))}",
        f"Description: {job.get('description','')}",
    ]
    return "\n".join([p for p in parts if p.strip()])


# ----------------------------- PAGE -----------------------------

style_ui()

# Sidebar (minimal)
with st.sidebar:
    st.subheader("Settings")
    st.caption(f"Python: {sys.executable}")
    primary_link = st.text_input("Primary portfolio link", value="https://sricharanbyreddy.online/")
    extra_links = st.text_input("Extra links (comma-sep)", value="https://github.com/Sricharanbyreddy9")
    user_terms_csv = st.text_input("Extra tech terms (comma-sep)", value="")
    USER_TERMS: Set[str] = {t.strip().lower() for t in user_terms_csv.split(",") if t.strip()}
    allow_js = st.toggle("JS fallback (requests_html)", value=False)
    rebuild_store = st.toggle("Rebuild resume store", value=False)
    chain, portfolio, fallback_links = ensure_core(primary_link, extra_links, rebuild_store)

# Step 1 — URL input (starts EMPTY so you paste your own link)
st.markdown("### 1) Job URL")
col_url, col_btn = st.columns([1.6, 0.4])

with col_url:
    url = st.text_input(
        "Paste the job posting URL",
        value="",  # <-- EMPTY default (no prefilled example)
        placeholder="https://careers.company.com/job/xyz",
        label_visibility="collapsed",
    )

with col_btn:
    fetch_btn = st.button("Fetch & Extract", use_container_width=True)

st.session_state.setdefault("jobs", [])
st.session_state.setdefault("selected_key", None)

# Step 2 — Fetch & extract
if fetch_btn:
    if not url.strip():
        st.warning("Paste a job URL first.")
    else:
        st.session_state.jobs = []
        st.session_state.selected_key = None

        with st.spinner("Fetching page…"):
            raw = fetch_job_text(url, allow_js=allow_js)

        if not raw:
            st.error("Could not fetch readable content. Enable **JS fallback** or paste the JD below.")
        else:
            with st.spinner("Cleaning text…"):
                cleaned = clean_text(raw)

            with st.spinner("Extracting posting(s)…"):
                jobs = chain.extract_jobs(cleaned)

            # Heuristic fallback if extractor returns nothing
            if not jobs:
                job = heuristic_job_from_text(
                    cleaned, url,
                    resume_text=portfolio.resume_text,
                    extra_terms=USER_TERMS
                )
                if job:
                    jobs = [job]
                    st.info("Used heuristic fallback to build a posting from the page text.")

            if not jobs:
                st.warning("Still couldn't extract a posting. Paste the JD manually below.")
            else:
                st.success(f"Found {len(jobs)} posting(s).")
                st.session_state.jobs = jobs

# Manual JD paste fallback
with st.expander("Alternatively, paste the full Job Description"):
    jd_text = st.text_area("Job Description", height=180, placeholder="Paste the JD text here…")
    if st.button("Extract from pasted JD"):
        if jd_text.strip():
            cleaned = clean_text(jd_text)
            jobs = chain.extract_jobs(cleaned)
            if not jobs:
                job = heuristic_job_from_text(
                    cleaned, url="(pasted)",
                    resume_text=portfolio.resume_text,
                    extra_terms=USER_TERMS
                )
                if job:
                    jobs = [job]
                    st.info("Used heuristic fallback to build a posting from the pasted JD.")
            if not jobs:
                st.error("Could not parse a posting from the pasted text.")
            else:
                st.success(f"Found {len(jobs)} posting(s) from pasted text.")
                st.session_state.jobs = jobs
        else:
            st.info("Paste some JD text first.")

# Step 3 — Select posting
if st.session_state.jobs:
    st.markdown("### 2) Select a posting")
    st.session_state.job_map = {}
    for i, j in enumerate(st.session_state.jobs, start=1):
        with st.container():
            st.markdown(f"**{i}. {j.get('title','(no title)')}**  <span class='pill'>Posting</span>", unsafe_allow_html=True)
            cc = st.columns(3)
            cc[0].write(f"**Location:** {j.get('location') or '—'}")
            cc[1].write(f"**Type:** {j.get('employment_type') or '—'}")
            cc[2].write(f"**Team:** {j.get('team') or '—'}")
            if j.get("skills"):
                st.write("**Skills:** " + ", ".join(j["skills"]))
            if j.get("apply_url"):
                st.link_button("Apply", j["apply_url"], use_container_width=False)
            st.session_state.job_map[f"{i}: {j.get('title','')}"] = j
            st.divider()

    options = list(st.session_state.job_map.keys())
    st.session_state.selected_key = st.selectbox("Compose email for:", options, index=0 if options else None)

# Step 4 — Generate email
if st.session_state.get("selected_key"):
    job = st.session_state.job_map[st.session_state.selected_key]
    job_description = job_to_description(job)

    # Query portfolio links with detected skills; fallback to sidebar links
    query_sentence = " ".join(job.get("skills") or []) or job.get("title", "")
    link_candidates = portfolio.query_links(query_sentence) or fallback_links

    st.markdown("### 3) Tailored email")
    with st.spinner("Writing a concise, resume-grounded email…"):
        email_text = chain.write_mail(
            job_description=job_description,
            resume_text=portfolio.resume_text,
            your_name="Sri Charan Reddy",
            title="Software Engineer (Full-Stack & GenAI/ML)",
            years_exp=4,
            years_ai_ml=2,
            link_candidates=link_candidates,
        )

    st.text_area("Email (editable)", value=email_text, height=300, label_visibility="collapsed")
    cdl, clinks = st.columns([0.6, 0.4])
    with cdl:
        st.download_button(
            "⬇️ Download .txt",
            data=email_text,
            file_name="cold_email.txt",
            mime="text/plain",
            use_container_width=True
        )
    with clinks:
        st.code("\n".join(link_candidates), language="text")

st.divider()
st.caption("Flexible skill mining • Heuristic fallback • Clean UI • Streamlit + LangChain + Groq + Chroma")
