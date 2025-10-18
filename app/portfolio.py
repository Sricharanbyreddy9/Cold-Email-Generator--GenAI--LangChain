# app/portfolio.py
# Build & query a Chroma collection from YOUR resume PDF (no CSV, no embeddings)

import re
import uuid
from pathlib import Path
from typing import List, Optional

import chromadb
from PyPDF2 import PdfReader


# keep tokens like: java, c++, .net, node.js
TECH_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,}")
STOPWORDS = {
    "experience", "experienced", "expertise", "expert", "worked", "work", "knowledge",
    "with", "in", "on", "of", "for", "and", "the", "a", "an", "as", "at", "to", "using",
    "have", "has", "had", "years", "year", "months", "month", "proficient", "strong",
    "good", "solid", "hands-on", "familiar", "background", "skill", "skills"
}

APP_DIR = Path(__file__).resolve().parent
RESUME_PATH_DEFAULT = APP_DIR / r"resource\Sri Charan Reddy Software_Engineer_Resume.pdf"  # your file
VECTOR_DIR_DEFAULT = APP_DIR.parent / "vectorstore"  # persisted DB folder at project root


class Portfolio:
    """
    Uses your resume PDF to create a lightweight searchable store in Chroma.
    - Splits the resume into small text units and saves them with your link in metadata.
    - Lets you query via natural sentences like "experience in Java" and returns your link.
    """

    def __init__(
        self,
        pdf_path: Path | str = RESUME_PATH_DEFAULT,
        link: str = "https://sricharanbyreddy.online/",
        vector_dir: Path | str = VECTOR_DIR_DEFAULT,
        collection_name: str = "portfolio",
        reset: bool = False,   # set True to rebuild from scratch
    ):
        self.pdf_path = Path(pdf_path)
        self.link = link
        self.vector_dir = Path(vector_dir)
        self.collection_name = collection_name

        # Read resume once
        self.resume_text = self._read_pdf(self.pdf_path)

        # Chroma setup
        self.chroma = chromadb.PersistentClient(str(self.vector_dir))
        if reset:
            try:
                self.chroma.delete_collection(self.collection_name)
            except Exception:
                pass
        self.collection = self.chroma.get_or_create_collection(self.collection_name)

        # Populate collection if empty
        if self.collection.count() == 0:
            self._index_resume_text()

    # ----------------- internal helpers -----------------

    def _read_pdf(self, path: Path) -> str:
        reader = PdfReader(str(path))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return re.sub(r"\s+", " ", text).strip().lower()  # normalize for contains-search

    def _split_units(self, text: str) -> List[str]:
        # split on bullets/line breaks, then on sentence boundaries
        rough = re.split(r"[•\n\r;]+", text)
        units: List[str] = []
        for r in rough:
            parts = re.split(r"(?<=[.!?])\s+(?=[a-z])", r.strip())  # after punctuation followed by a word
            for p in parts:
                s = p.strip()
                if len(s) >= 8:
                    units.append(s)
        return units or [text]

    def _index_resume_text(self):
        units = self._split_units(self.resume_text)
        B = 100
        for i in range(0, len(units), B):
            chunk = units[i:i + B]
            self.collection.add(
                documents=chunk,
                metadatas=[{"link": self.link, "source_pdf": str(self.pdf_path)} for _ in chunk],
                ids=[str(uuid.uuid4()) for _ in chunk],
            )

    def _extract_tokens(self, sentence: str) -> List[str]:
        toks = []
        for t in TECH_TOKEN_RE.findall(sentence.lower()):
            t = t.strip(".-")
            if not t or t in STOPWORDS:
                continue
            toks.append(t)
        # de-dupe preferring longer tokens
        seen, ordered = set(), []
        for t in sorted(toks, key=len, reverse=True):
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        return ordered

    # ----------------- public API -----------------

    def has_skill(self, skill: str) -> bool:
        return re.search(rf"\b{re.escape(skill.lower())}\b", self.resume_text) is not None

    def query_links(self, sentence: str, n_results: int = 3) -> List[str]:
        """
        Given a natural sentence (e.g., 'experience in Java'), extract skill tokens,
        confirm they exist in the resume, and return your link from Chroma metadata.
        Typically you'll get your single canonical link back.
        """
        tokens = self._extract_tokens(sentence)

        links: List[str] = []
        for tok in tokens:
            # only consider rows whose document contains that token
            res = self.collection.query(
                query_texts=[tok],
                n_results=n_results,
                include=["metadatas"],
                where_document={"$contains": tok},
            )
            for group in res.get("metadatas", []):
                for m in group or []:
                    if m and "link" in m:
                        links.append(m["link"])
            if links:
                break  # stop after first strong token

        # unique preserve order
        seen, uniq = set(), []
        for l in links:
            if l not in seen:
                seen.add(l)
                uniq.append(l)
        return uniq


# -------------- quick local test --------------
if __name__ == "__main__":
    p = Portfolio(
        pdf_path=RESUME_PATH_DEFAULT,
        link="https://sricharanbyreddy.online/",
        vector_dir=VECTOR_DIR_DEFAULT,
        collection_name="portfolio",
        reset=False,  # flip to True if you want to rebuild the index
    )
    print("Has Java?", p.has_skill("Java"))
    print("Links for 'experience in Java':", p.query_links("I have experience in Java"))
    print("Links for 'expertise in LangChain':", p.query_links("Expertise in LangChain"))
