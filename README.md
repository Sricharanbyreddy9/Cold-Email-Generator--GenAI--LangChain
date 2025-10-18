# 📧 Cold Email Generator — Streamlit + LangChain + Groq + Chroma

Turn any job posting URL into a **concise, resume-grounded cold email** that reads human and specific.  
It fetches job pages, extracts or reconstructs the role, anchors to your **PDF resume** as the source of truth, and writes a short letter-style email with measurable impact.

---

## ✨ Highlights

- **Paste a job URL → Email in 1–2 clicks**
- **Robust fetching** (LangChain loader → requests → cloudscraper → optional JS render fallback)
- **LLM extractor** returns **pure JSON**; **heuristic fallback** if a site blocks scraping
- **Resume-grounded** generation to avoid hallucinations (uses your PDF as source of truth)
- **Chroma** mini-portfolio index to pick a relevant link (portfolio/GitHub) per JD
- **Clean UI** with a 3-step flow and one-click download to `.txt`
- **Secret-safe**: `.env` for API keys; `.gitignore` excludes env, notebooks, vectorstore

---

## 🧭 App Flow

1. **Paste URL** → page text fetched & cleaned  
2. **Extract Posting** → LLM returns pure JSON; fallback builds one heuristically  
3. **Mine Skills** → overlap JD ∩ resume tokens (no fixed skill list)  
4. **Pick Links** → Chroma (seeded from your resume) + sidebar links  
5. **Write Email** → letter-style (160–220 words), resume-grounded, includes one relevant link  
6. **Review & Download** → edit and export as `.txt`

---

## 🗂️ Project Structure
```
Cold-Email-Generator/
├─ app/
│ ├─ main.py # Streamlit UI (fetch → extract → email)
│ ├─ chains.py # Chain class (extract_jobs, write_mail, find_skill_in_resume)
│ ├─ portfolio.py # Build/query Chroma from your PDF resume
│ ├─ utils.py # Text cleaners and helpers
│ └─ resource/
│ └─ Sri Charan Reddy Software_Engineer_Resume.pdf
├─ .env # GROQ_API_KEY (never commit)
├─ .gitignore # Protects secrets, venv, notebooks, vectorstore
└─ vectorstore/ # On-disk Chroma DB (ignored by git)

```

---

## 🧱 Tech Stack

---
| Layer        | Tools / Libraries |
|-------------|--------------------|
| UI          | Streamlit          |
| LLM         | Groq via `langchain_groq` (`llama-3.3-70b-versatile`) |
| Orchestration | LangChain (prompts, parsing) |
| Fetching    | LangChain `WebBaseLoader`, `requests`, `cloudscraper`, `requests_html` |
| Indexing    | Chroma (persistent, local) |
| PDF         | `pypdf`            |
---

---

## 🔍 What’s Inside (High-Level)

---
| Area | What it contains |
|------|------------------|
| UI (Streamlit) | A clean 3-step flow: paste URL → extract posting → generate email; manual JD fallback; download button; link previews. |
| LLM Chains | Two prompts: (1) **Job extractor** that returns pure JSON; (2) **Email writer** that creates a letter-style email grounded strictly in your resume and the JD. |
| Portfolio Index (Chroma) | A tiny on-disk store built **directly from your resume PDF** (no CSV needed) to surface a relevant link per JD. |
| Fetchers | Robust pipeline to get readable text from career sites, with a JS rendering toggle for stubborn pages. |
| Utilities | Text cleaning/normalization to remove HTML artifacts and keep inputs model-friendly. |
| Security & Hygiene | `.env` for API keys; `.gitignore` excludes env, notebooks, vectorstore; guidance for secret-scanning and safe pushes. |
---

---

## 🧠 How It Works (End-to-End)

1. **Fetching**  
   Multiple strategies (LangChain loader → requests → cloudscraper → optional JS render) ensure we get readable text from most career sites.

2. **Extraction**  
   An LLM converts the page into a **JSON job object** (title, location, skills, description, apply URL).  
   If a site blocks scraping, a **heuristic fallback** reconstructs a usable posting from the text.

3. **Grounding**  
   Your resume PDF is parsed and used as the single source of truth. The app intersects JD tokens with resume tokens—no fixed skill list—so it stays flexible.

4. **Link Selection**  
   The Chroma store (seeded from your resume) and sidebar links help pick **one** link (portfolio/GitHub) that best supports the JD.

5. **Email Composition**  
   A letter-style email (160–220 words) that mirrors JD needs, cites a concrete resume outcome, includes one link, and proposes a short call with a 30-day goal.

---

## 🏗️ Architecture Overview

---
| Layer | Responsibility |
|------|-----------------|
| Streamlit App | Orchestrates the flow, renders UI, handles inputs/actions. |
| Chain (LLM) | Prompts for job extraction (JSON) and email generation (letter-style). |
| Portfolio | Reads your **resume PDF**, seeds Chroma, and answers “which link best matches this JD?” |
| Fetchers | Try multiple strategies to obtain readable text from career sites. |
| Utils | Clean and normalize raw content (HTML entities, whitespace, URLs). |
---

---

## 🔐 Security & Privacy

- **No secrets in code**: Groq API key lives in `.env` only; never commit it.
- **Local vector store**: `vectorstore/` is ignored by git and rebuilt on first run if needed.
- **Resume stays local**: Your PDF is processed locally; Chroma is stored on disk.
- **Push protection**: If a key is ever committed by accident, rotate it and re-init a clean history before pushing.

---

## 🚀 What This Demonstrates

- Practical **ingestion → parsing → grounding → generation** pipeline
- **Non-hallucination** strategy by strictly anchoring to resume text
- **Robust web ingestion** with graceful fallbacks
- **Product polish**: concise, skimmable, role-aligned emails
- **Security hygiene**: `.env`, `.gitignore`, and secret scanning readiness

---

## 🧪 Typical Usage

- Paste a JD URL → extract or reconstruct the posting  
- Confirm or adjust (optional)  
- Generate the email tailored to that role  
- Edit lightly, download, and send

---

## ⚠️ Limitations

- Some gated/React-heavy career sites still require the JS fallback or manual paste
- Tuned for English JDs
- Link selection intentionally conservative to avoid over-claiming

---

## 🗺️ Roadmap Ideas

- Embedding-based similarity to enhance link/skill selection (with guardrails)  
- Tone presets (founder-style, enterprise, research)  
- ATS-friendly variants (plain-text pitch)  
- Batch mode to process multiple job links and export a set of emails

---

## 📄 License

MIT — free to use and modify.  
If you build on this, a star ⭐️ would be awesome!
