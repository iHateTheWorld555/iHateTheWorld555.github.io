#!/usr/bin/env python3
"""One-off backfill via OAI-PMH while the arxiv API is rate-limited (429).

Reuses scrape_papers.py's filtering and markdown generation. The OAI-PMH
endpoint (export.arxiv.org/oai2) is not under the same rate-limit as
/api/query right now. Papers are filtered by their original `created`
date, not the OAI datestamp (which reflects last modification).
"""

import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import scrape_papers as sp  # noqa: E402

OAI = "https://export.arxiv.org/oai2"
SETS = ["eess:eess", "cs:cs"]
import os
FROM = os.getenv("OAI_FROM", "2026-09-18")
UNTIL = os.getenv("OAI_UNTIL", "2026-09-27")
ARXIV_NS = "http://arxiv.org/OAI/arXiv/"
OAI_NS = "http://www.openarchives.org/OAI/2.0/"

PAPERS_DIR = REPO_ROOT / "_papers"


def oai_get(params: dict, tries: int = 5) -> str:
    url = OAI + "?" + urllib.parse.urlencode(params)
    for attempt in range(1, tries + 1):
        # urllib's TLS fingerprint gets a bare 406 from Fastly on this network;
        # curl passes, so shell out to it (same story as scrape_papers.py's note).
        proc = subprocess.run(
            ["curl", "-sL", "--max-time", "180", url],
            capture_output=True, text=True, timeout=200,
        )
        body = proc.stdout
        if proc.returncode == 0 and body.startswith("<?xml"):
            return body
        err = (proc.stderr or body[:200]).strip()
        print(f"  curl attempt {attempt}/{tries} failed: {err[:150]}")
        if attempt >= tries:
            raise RuntimeError(f"OAI request failed after {tries} attempts: {err[:200]}")
        time.sleep(20 * attempt)
    raise RuntimeError("OAI request exhausted retries")


def parse_records(xml_body: str) -> list[dict]:
    """Extract papers with created date within [FROM, UNTIL]."""
    root = ET.fromstring(xml_body)
    ns = {"oai": OAI_NS, "ax": ARXIV_NS}
    out = []
    for rec in root.iter(f"{{{OAI_NS}}}record"):
        ar = rec.find(f".//{{{ARXIV_NS}}}arXiv")
        if ar is None:
            continue
        created = (ar.findtext(f"{{{ARXIV_NS}}}created") or "")[:10]
        updated = (ar.findtext(f"{{{ARXIV_NS}}}updated") or "")[:10]
        if not (FROM <= created <= UNTIL):
            continue  # old paper merely modified in this window — skip
        arxiv_id = (ar.findtext(f"{{{ARXIV_NS}}}id") or "").strip()
        title = sp.normalise(ar.findtext(f"{{{ARXIV_NS}}}title"))
        abstract = sp.normalise(ar.findtext(f"{{{ARXIV_NS}}}abstract"))
        categories = (ar.findtext(f"{{{ARXIV_NS}}}categories") or "").split()
        authors = []
        for a_el in ar.findall(f"{{{ARXIV_NS}}}authors/{{{ARXIV_NS}}}author"):
            key = a_el.findtext(f"{{{ARXIV_NS}}}keyname") or ""
            fore = a_el.findtext(f"{{{ARXIV_NS}}}forenames") or ""
            if key or fore:
                authors.append(sp.normalise(f"{fore} {key}".strip()))
        out.append({
            "title": title,
            "date": created,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "authors": ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else ""),
            "categories": ", ".join(categories),
            "primary_category": categories[0] if categories else "",
            "summary": abstract,
            "comment": "",  # OAI has no comment field
        })
    return out


def main():
    all_papers = []
    for s in SETS:
        print(f"== set={s} ==")
        token = None
        while True:
            params = {
                "verb": "ListRecords",
                "metadataPrefix": "arXiv",
                "set": s,
                "from": FROM,
                "until": UNTIL,
            }
            if token:
                params = {"verb": "ListRecords", "resumptionToken": token}
            body = oai_get(params)
            all_papers.extend(parse_records(body))
            m = re.search(
                r'<resumptionToken[^>]*>([^<]*)</resumptionToken>', body)
            token = (m.group(1) or "").strip() if m else None
            if not token:
                break
            time.sleep(5)
            print(f"  next page ({token[:30]}...)")

    print(f"Raw records in window: {len(all_papers)}")
    all_papers = sp.deduplicate(all_papers)
    all_papers = sp.filter_excluded(all_papers)
    all_papers = sp.filter_cross_by_title(all_papers)
    print(f"After filters: {len(all_papers)}")

    by_date: dict[str, list[dict]] = {}
    for p in all_papers:
        by_date.setdefault(p["date"], []).append(p)

    wrote = 0
    for date, day_papers in sorted(by_date.items()):
        out_path = PAPERS_DIR / f"{date}.md"
        if out_path.exists() and "**Score:" in out_path.read_text(encoding="utf-8"):
            print(f"Skipping {out_path.name} (already scored)")
            continue
        md = sp.generate_markdown(date, day_papers)
        out_path.write_text(md, encoding="utf-8")
        wrote += 1
        print(f"Wrote {out_path.name} ({len(day_papers)} papers)")
    print(f"Done: {wrote} files written")


if __name__ == "__main__":
    main()
