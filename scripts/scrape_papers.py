#!/usr/bin/env python3
"""Scrape daily arxiv papers on audio, speech, music, and acoustics.

Based on retry/backoff patterns from Kiraaa1/ArXic-AI-Paper-Digest-Agent.

Search strategy:
  1. Full crawl of core categories: cs.SD, eess.AS
  2. Keyword-filtered crawl of cross categories: cs.CL, cs.AI, cs.MM,
     cs.CV, cs.LG, eess.SP — keywords searched in abstract

Output: one markdown file per day in _papers/YYYY-MM-DD.md
"""

import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO_ROOT / "_papers"

# --- Configuration ---
CORE_CATEGORIES = ["cs.SD", "eess.AS"]
CROSS_CATEGORIES = ["cs.CL", "cs.AI", "cs.MM", "cs.CV", "cs.LG", "eess.SP"]
KEYWORDS = [
    "audio", "speech", "voice", "sound", "acoustic", "music",
    "TTS", "ASR", "speaker", "codec", "deepfake", "watermark",
    "prosody", "phoneme", "diarization", "vocoder", "utterance",
    "spoken", "waveform", '"mel spectrogram"', "singing",
    "source separation", "timbre", "resynthesis", "text-to-speech",
    "speech enhancement", "speech synthesis", "speech recognition",
    "voice conversion", "audio generation", "sound generation",
]
# Topics to exclude — not relevant to general audio/speech research
EXCLUDE_PATTERNS = [
    # Pathological / clinical / medical
    r"\bdysarthri", r"\bpatholog", r"\bclinical\b", r"\bpatient\b", r"\bdisease",
    r"\bcancer", r"\bcough", r"\bheart sound", r"\blung sound",
    r"\bdementia\b", r"\bAlzheimer\b", r"\bcognitive decline\b",
    # Pediatric / elderly-specific
    r"\bchild\b", r"\bpediatric", r"\binfant\b", r"\belderly\b", r"\baging voice",
    # Niche languages (keep: English, Chinese, multilingual as concept)
    r"\bVietnamese\b", r"\bGreek\b", r"\bTamil\b", r"\bSwahili\b",
    r"\bIcelandic\b", r"\bBasque\b", r"\bMalayalam\b", r"\bKannada\b",
    r"\bTangkhul\b", r"\bAlgerian\b",
    # Pure hardware / physics / engineering (not ML)
    r"\bunderwater\b", r"\bAUV\b", r"\bmarine\b", r"\bsonar\b",
    r"\broom equalization\b", r"\bloudspeaker\b", r"\bheadrest\b",
    r"\bacoustic attack", r"\bover-the-air attack",
    # Security / fraud (not audio ML)
    r"\bfraud\b", r"\bfraud detection\b",
    # Non-audio domains that leak via cross-category keywords
    r"\bspacecraft\b", r"\bGNC\b", r"\bfinitely axiomatiz",
    r"\bAFDM\b", r"\bISAC\b",
    # Video codec (not audio codec)
    r"\bvideo codec\b", r"\blearned video\b",
    # Facial animation (edge case: speech-driven but not audio research)
    r"\bfacial animation\b", r"\bface animation\b", r"\btalking head\b",
]

EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

# For cross-category papers: title must contain audio keywords
TITLE_AUDIO_KEYWORDS = re.compile(
    r"\b(audio|speech|voice|sound|acoustic|music|TTS|ASR|speaker|vocoder|"
    r"phoneme|prosody|diarization|utterance|spoken|waveform|singing|codec)\b",
    re.IGNORECASE,
)
CORE_CATEGORIES_SET = set(CORE_CATEGORIES)

ARXIV_API = "https://export.arxiv.org/api/query"
PAGE_SIZE = 200  # max results per request (arxiv max=2000, 200 is safer)
LOOKBACK_DAYS = int(os.getenv("PAPER_SCRAPE_LOOKBACK_DAYS", "7"))
MAX_RETRIES = 7
BACKOFF_BASE = 15.0
BACKOFF_CAP = 120.0
RETRY_429_MIN = 30.0
REQUEST_TIMEOUT = 120.0
MIN_REQUEST_INTERVAL = 3.0  # arxiv ToU: no more than 1 request per 3 seconds

# ArXiv throttles generic UAs aggressively, especially from GitHub Actions IPs.
USER_AGENT = (
    "AudioPaperDigestBot/1.0 "
    "(+https://github.com/iHateTheWorld555/iHateTheWorld555.github.io)"
)

NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
WS_RE = re.compile(r"\s+")
RETRY_STATUSES = {429, 500, 502, 503, 504}


LIQUID_RE = re.compile(r"\{%.*?%\}|\{\{.*?\}\}")

def normalise(text: str | None) -> str:
    if text is None:
        return ""
    text = WS_RE.sub(" ", text).strip()
    # Escape Liquid template delimiters that could break Jekyll builds
    text = LIQUID_RE.sub("", text)
    # Escape angle brackets that could be interpreted as HTML
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text


def backoff(attempt: int) -> float:
    return min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)


_last_request_time: float = 0


def request_with_retry(client: httpx.Client, params: dict) -> str:
    """GET arxiv API with retry/backoff on 429, 5xx, and network errors."""
    global _last_request_time
    # Enforce arxiv ToU: no more than 1 request per 3 seconds
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.get(ARXIV_API, params=params)
        except httpx.RequestError as exc:
            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    f"ArXiv failed after {MAX_RETRIES} attempts: {exc}"
                ) from exc
            wait = backoff(attempt)
            log.warning("ArXiv network error (%s) attempt %d/%d, wait %.1fs",
                        type(exc).__name__, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue

        if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            wait = backoff(attempt)
            if resp.status_code == 429:
                wait = max(wait, RETRY_429_MIN * attempt)
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    pass
            wait = min(wait, BACKOFF_CAP)
            log.warning("ArXiv returned %d attempt %d/%d, wait %.1fs",
                        resp.status_code, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue

        if resp.status_code in RETRY_STATUSES:
            raise RuntimeError(f"ArXiv returned {resp.status_code} after {MAX_RETRIES} attempts")

        resp.raise_for_status()
        _last_request_time = time.time()
        return resp.text

    raise RuntimeError("ArXiv request exhausted retries")


def fetch_papers(query: str, max_results: int | None = None) -> list[dict]:
    """Fetch papers from arxiv API with pagination."""
    client = httpx.Client(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    all_papers = []
    start = 0
    parse_failures = 0
    total_results: int | None = None

    try:
        while True:
            page_size = PAGE_SIZE
            if max_results is not None:
                page_size = min(PAGE_SIZE, max_results - start)
                if page_size <= 0:
                    break
            params = {
                "search_query": query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": str(page_size),
                "start": str(start),
            }
            log.info("Fetching start=%d max=%d", start, page_size)
            body = request_with_retry(client, params)

            try:
                root = ET.fromstring(body)
            except ET.ParseError:
                parse_failures += 1
                if parse_failures >= 3:
                    raise RuntimeError("ArXiv returned non-Atom body 3 times, giving up")
                log.warning("ArXiv returned non-Atom body (attempt %d/3), retrying", parse_failures)
                continue

            if total_results is None:
                total_text = root.findtext(f"{{{OPENSEARCH_NS}}}totalResults")
                total_results = int(total_text or 0)
                if max_results is not None:
                    total_results = min(total_results, max_results)
                log.info("Query reports %d total results", total_results)

            entries = root.findall("atom:entry", NS)
            if not entries:
                break

            page_count = 0
            for entry in entries:
                raw_url = (entry.find("atom:id", NS).text or "").strip()
                if not raw_url or "Error" in raw_url:
                    continue

                url = raw_url.replace("http://", "https://", 1)
                title = normalise(entry.find("atom:title", NS).text)
                published = (entry.find("atom:published", NS).text or "")[:10]
                authors = []
                for a_el in entry.findall("atom:author", NS):
                    name_el = a_el.find("atom:name", NS)
                    if name_el is not None and name_el.text:
                        authors.append(normalise(name_el.text))
                cats = [c.get("term") for c in entry.findall("atom:category", NS)]
                summary = normalise(entry.find("atom:summary", NS).text)
                comment_el = entry.find("arxiv:comment", NS)
                comment = normalise(comment_el.text) if comment_el is not None and comment_el.text else ""
                primary_el = entry.find("arxiv:primary_category", NS)
                primary_cat = primary_el.attrib.get("term") if primary_el is not None else None

                all_papers.append({
                    "title": title,
                    "date": published,
                    "arxiv_url": url,
                    "authors": ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else ""),
                    "categories": ", ".join(cats),
                    "primary_category": primary_cat or "",
                    "summary": summary,
                    "comment": comment,
                })
                page_count += 1

            start += page_size
            if page_count < page_size or start >= (total_results or 0):
                break
            time.sleep(3)  # polite delay between pages
    finally:
        client.close()

    return all_papers


def build_queries() -> tuple[str, str]:
    """Build core + cross-category queries."""
    core_q = " OR ".join(f"cat:{c}" for c in CORE_CATEGORIES)
    kw_q = " OR ".join(f"abs:{kw}" for kw in KEYWORDS)
    cross_cat_q = " OR ".join(f"cat:{c}" for c in CROSS_CATEGORIES)
    cross_q = f"({cross_cat_q}) AND ({kw_q})"
    return core_q, cross_q


def deduplicate(papers: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in papers:
        if p["arxiv_url"] not in seen:
            seen.add(p["arxiv_url"])
            unique.append(p)
    return unique


def filter_recent(papers: list[dict], days: int = 3) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [p for p in papers if p["date"] >= cutoff]


def recent_date_filter(days: int = 3) -> str:
    """Return an API-side UTC date window so pagination cannot truncate recency."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return f"submittedDate:[{cutoff:%Y%m%d}0000 TO {now:%Y%m%d}2359]"


def filter_excluded(papers: list[dict]) -> list[dict]:
    """Remove papers on niche/clinical/irrelevant topics."""
    kept = []
    for p in papers:
        text = f"{p['title']} {p['summary']}"
        if EXCLUDE_RE.search(text):
            log.debug("Excluded: %s", p["title"][:80])
        else:
            kept.append(p)
    excluded = len(papers) - len(kept)
    if excluded:
        log.info("Filtered out %d excluded-topic papers", excluded)
    return kept


def filter_cross_by_title(papers: list[dict]) -> list[dict]:
    """Cross-category papers must have audio keywords in title."""
    kept = []
    for p in papers:
        cats = [c.strip() for c in p.get("categories", "").split(",")]
        # Core audio categories always pass
        if any(c in CORE_CATEGORIES_SET for c in cats):
            kept.append(p)
            continue
        # Cross-category: title must contain audio keywords
        if TITLE_AUDIO_KEYWORDS.search(p["title"]):
            kept.append(p)
        else:
            log.debug("Cross-cat filtered (no title keyword): %s", p["title"][:80])
    filtered = len(papers) - len(kept)
    if filtered:
        log.info("Filtered out %d cross-category papers (no title keyword)", filtered)
    return kept


def generate_markdown(date: str, papers: list[dict]) -> str:
    """Generate Jekyll markdown for one day's papers."""
    # Sort: core audio categories first, then cross-category
    core_cats = set(CORE_CATEGORIES)
    papers.sort(key=lambda p: (
        0 if any(c in core_cats for c in p["categories"].split(", ")) else 1,
        p["categories"],
        p["title"],
    ))

    lines = [
        "---",
        f"date: {date}",
        f'title: "Daily Papers {date}"',
        "layout: daily-papers",
        "author_profile: false",
        "categories: papers",
        "---",
        "",
        f"# Daily Papers — {date}",
        "",
        f"**{len(papers)} papers** on audio, speech, music, and acoustics.",
        "",
    ]

    for i, p in enumerate(papers, 1):
        lines.append(f'## {i}. [{p["title"]}]({p["arxiv_url"]})')
        lines.append("")
        lines.append(f'**Authors:** {p["authors"]}')
        lines.append("")
        lines.append(f'**Categories:** `{p["categories"]}`')
        if p["comment"]:
            lines.append(f'  | {p["comment"]}')
        lines.append("")
        lines.append(f'> {p["summary"]}')
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    PAPERS_DIR.mkdir(exist_ok=True)

    core_q, cross_q = build_queries()
    date_q = recent_date_filter(days=LOOKBACK_DAYS)

    log.info("Fetching core categories: %s", CORE_CATEGORIES)
    papers = fetch_papers(f"({core_q}) AND {date_q}")
    log.info("  Got %d papers from core categories", len(papers))

    time.sleep(5)  # delay between queries

    log.info("Fetching cross categories with keywords")
    cross_papers = fetch_papers(f"({cross_q}) AND {date_q}")
    log.info("  Got %d papers from cross categories", len(cross_papers))

    all_papers = deduplicate(papers + cross_papers)
    all_papers = filter_recent(all_papers, days=LOOKBACK_DAYS)
    all_papers = filter_excluded(all_papers)
    all_papers = filter_cross_by_title(all_papers)
    log.info("Total after dedup+filter+exclude: %d papers", len(all_papers))

    if not all_papers:
        log.warning("No papers found!")
        sys.exit(0)

    # Group by date
    by_date: dict[str, list[dict]] = {}
    for p in all_papers:
        by_date.setdefault(p["date"], []).append(p)

    for date, day_papers in by_date.items():
        out_path = PAPERS_DIR / f"{date}.md"
        # Skip if file already exists with scores (avoid overwriting scored data)
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            if "**Score:" in existing:
                log.info("Skipping %s (already scored, %d papers)", out_path, len(day_papers))
                continue
            else:
                log.info("Overwriting %s (exists but not scored)", out_path)
        md = generate_markdown(date, day_papers)
        out_path.write_text(md, encoding="utf-8")
        log.info("Wrote %s (%d papers)", out_path, len(day_papers))

    log.info("Done!")


if __name__ == "__main__":
    main()
