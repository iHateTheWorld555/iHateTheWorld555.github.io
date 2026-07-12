#!/usr/bin/env python3
"""Project Claude Code full-paper reviews back into daily paper digests."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPERS_DIR = REPO_ROOT / "_papers"
REVIEWS_DIR = REPO_ROOT / "_paper_reviews"

AXIS_NAMES = {
    "一": "Obj",
    "二": "Id",
    "三": "Ind",
    "四": "Comp",
    "五": "Eff",
    "六": "Nov",
    "七": "Rep",
}


@dataclass(frozen=True)
class ReviewDigest:
    total: float
    axes: dict[str, int]
    strength: str
    weakness: str


def clean_excerpt(text: str, limit: int = 220) -> str:
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -—:：")
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("。", 1)[0].rstrip("，,；; ")
    return (cut or text[:limit]).rstrip() + "。"


def section_line(text: str, label: str) -> str | None:
    patterns = [
        rf"^-\s*\*\*{re.escape(label)}\s*[:：][^*]*\*\*\s*[—-]\s*(.+)$",
        rf"^-\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[:：]\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return clean_excerpt(match.group(1))
    return None


def first_improvement(text: str) -> str | None:
    marker = re.search(
        r"^(?:##\s+|\*\*)?(?:核心问题摘要|核心改进建议|关键缺陷总结|主要不足|核心问题)[^\n]*$",
        text,
        re.MULTILINE,
    )
    if not marker:
        return None
    same_line = re.search(r"[:：]\s*(.+?)(?:\*\*)?$", marker.group(0))
    if same_line and same_line.group(1).strip():
        return clean_excerpt(same_line.group(1))
    tail = text[marker.end():]
    match = re.search(r"^\s*(?:\d+\.|[-*])\s*(?:\[[^]]+\]\s*)?(.+)$", tail, re.MULTILINE)
    return clean_excerpt(match.group(1)) if match else None


def lowest_axis_evidence(text: str, axes: dict[str, int]) -> str | None:
    reverse = {value: key for key, value in AXIS_NAMES.items()}
    axis = min(axes, key=axes.get)
    numeral = reverse[axis]
    match = re.search(
        rf"^###\s+公理{numeral}[^\n]*\n(.*?)(?=^###\s+公理|^##\s+总评|^##\s+打分)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    evidence = re.search(r"^-\s*(?:\*\*)?依据(?:\*\*)?\s*[:：]\s*(.+)", match.group(1), re.MULTILINE)
    return clean_excerpt(evidence.group(1)) if evidence else None


def prose_summary(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"^##\s+总评\s*\n+(.*?)(?=^##\s+)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return None, None
    paragraph = re.sub(r"\s+", " ", match.group(1)).strip()
    if not paragraph or paragraph.startswith("-"):
        return None, None
    parts = re.split(r"主要问题在于[:：]", paragraph, maxsplit=1)
    strength = clean_excerpt(parts[0]) if parts[0] else None
    weakness = clean_excerpt(parts[1]) if len(parts) == 2 else None
    return strength, weakness


def load_review(path: Path, write_recovery: bool) -> tuple[str, ReviewDigest]:
    text = path.read_text(encoding="utf-8")
    try:
        digest = parse_review(text)
        if write_recovery:
            normalized = re.sub(
                r'^daily_score:.*$',
                f'daily_score: "{digest.total:.2f}/10"',
                text,
                count=1,
                flags=re.MULTILINE,
            )
            if normalized != text:
                path.write_text(normalized, encoding="utf-8")
                text = normalized
        return text, digest
    except ValueError as original_error:
        log_path = path.with_suffix(".log")
        if not log_path.exists():
            raise original_error
        candidates: list[str] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("type") != "assistant":
                continue
            candidate = "".join(
                chunk.get("text", "")
                for chunk in message.get("message", {}).get("content", [])
                if chunk.get("type") == "text"
            )
            if "加权总分" in candidate:
                candidates.append(candidate)
        for candidate in sorted(candidates, key=len, reverse=True):
            try:
                digest = parse_review(candidate)
            except ValueError:
                continue
            if write_recovery:
                front = re.match(r"(---\n.*?\n---\n+)", text, re.DOTALL)
                prefix = front.group(1) if front else ""
                recovered = prefix + candidate.strip() + "\n"
                recovered = re.sub(
                    r'^daily_score:.*$',
                    f'daily_score: "{digest.total:.2f}/10"',
                    recovered,
                    count=1,
                    flags=re.MULTILINE,
                )
                path.write_text(recovered, encoding="utf-8")
            return candidate, digest
        raise original_error


def parse_review(text: str) -> ReviewDigest:
    total_match = re.search(r"\*\*加权总分:\s*([\d.]+)\s*/\s*10\*\*", text)
    if not total_match:
        raise ValueError("missing weighted total")

    axes: dict[str, int] = {}
    for numeral, score in re.findall(
        r"^\|\s*([一二三四五六七])\s+[^|]+\|\s*[^|]+\|\s*([\d.]+)\s*\|",
        text,
        re.MULTILINE,
    ):
        axes[AXIS_NAMES[numeral]] = round(float(score))
    missing = set(AXIS_NAMES.values()) - set(axes)
    if missing:
        raise ValueError(f"missing axes: {', '.join(sorted(missing))}")

    strength = section_line(text, "Strength")
    weakness = section_line(text, "Weakness")
    prose_strength, prose_weakness = prose_summary(text)
    if not strength:
        strength = section_line(text, "方法价值") or section_line(text, "科学价值") or prose_strength
    if not weakness:
        weakness = first_improvement(text) or prose_weakness or lowest_axis_evidence(text, axes)
    if not strength or not weakness:
        raise ValueError("missing digest strength/weakness")

    return ReviewDigest(float(total_match.group(1)), axes, strength, weakness)


def review_path(date: str, arxiv_id: str, reviews_dir: Path = REVIEWS_DIR) -> Path:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", arxiv_id).strip("_")
    return reviews_dir / date / f"{stem}.md"


def score_block(date: str, arxiv_id: str, digest: ReviewDigest) -> str:
    axes = " ".join(f"{name}:{digest.axes[name]}" for name in AXIS_NAMES.values())
    review_url = f"/reviews/{date}/{review_path(date, arxiv_id).stem}/"
    return (
        f"\n**Score: {digest.total:.2f}/10** ({axes})\n"
        f"- **Strength:** {digest.strength}\n"
        f"- **Weakness:** {digest.weakness}\n"
        f"- **Full review:** [Claude Code 全文七公理审稿]({review_url})\n"
    )


SCORE_RE = re.compile(
    r"\n\*\*Score:\s*[\d.]+/10\*\*[^\n]*\n"
    r"(?:-\s+\*\*(?:Strength|Weakness|Full review):\*\*[^\n]*\n)*",
    re.MULTILINE,
)


def update_section(
    date: str,
    section: str,
    reviews_dir: Path,
    write_recovery: bool,
) -> tuple[str, float | None, Path | None]:
    header = re.search(r"^##\s+\d+\.\s+\[.+?\]\(https://arxiv\.org/abs/([^)]+)\)", section, re.MULTILINE)
    if not header:
        return section, None, None
    arxiv_id = header.group(1)
    path = review_path(date, arxiv_id, reviews_dir)
    if not path.exists():
        return section, None, path
    try:
        _, digest = load_review(path, write_recovery=write_recovery)
    except ValueError as exc:
        print(f"{date}/{arxiv_id}: invalid full review ({exc})")
        return SCORE_RE.sub("\n", section), None, path
    section = SCORE_RE.sub("\n", section)
    quote = re.search(r"^>\s", section, re.MULTILINE)
    if not quote:
        raise ValueError(f"{arxiv_id}: abstract block not found")
    section = section[:quote.start()].rstrip() + score_block(date, arxiv_id, digest) + "\n" + section[quote.start():].lstrip()
    return section, digest.total, path


def sync_file(path: Path, reviews_dir: Path = REVIEWS_DIR, write: bool = True) -> tuple[int, int]:
    date = path.stem
    content = path.read_text(encoding="utf-8")
    front = re.match(r"(---\n.*?\n---\n+)(.*)", content, re.DOTALL)
    if not front:
        raise ValueError(f"{path}: front matter not found")
    front_matter, body = front.groups()
    parts = re.split(r"(?=^##\s+\d+\.)", body, flags=re.MULTILINE)
    header, raw_sections = parts[0], parts[1:]

    updated: list[tuple[float | None, str]] = []
    synced = 0
    for raw in raw_sections:
        section, total, _ = update_section(date, raw, reviews_dir, write_recovery=write)
        updated.append((total, section))
        synced += total is not None

    updated.sort(key=lambda item: (item[0] is not None, item[0] or 0), reverse=True)
    rebuilt = front_matter + header
    for index, (_, section) in enumerate(updated, 1):
        rebuilt += re.sub(r"^##\s+\d+\.", f"## {index}.", section, count=1, flags=re.MULTILINE)

    scores = [total for total, _ in updated if total is not None]
    rebuilt = re.sub(r"avg_score: .*\n|top_score: .*\n|papers_scored: .*\n", "", rebuilt)
    if scores:
        stats = f"avg_score: {sum(scores) / len(scores):.1f}\ntop_score: {max(scores):.2f}\npapers_scored: {len(scores)}\n"
        rebuilt = re.sub(r"---\n\n# Daily", stats + "---\n\n# Daily", rebuilt, count=1)
    if write and rebuilt != content:
        path.write_text(rebuilt, encoding="utf-8")
    return synced, len(raw_sections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dates", nargs="*")
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--reviews-dir", default=str(REVIEWS_DIR))
    args = parser.parse_args()

    dates = args.dates or sorted(path.stem for path in PAPERS_DIR.glob("????-??-??.md"))
    incomplete: list[str] = []
    for date in dates:
        synced, total = sync_file(
            PAPERS_DIR / f"{date}.md",
            Path(args.reviews_dir),
            write=not args.check,
        )
        print(f"{date}: synced {synced}/{total} full reviews")
        if synced != total:
            incomplete.append(f"{date} ({synced}/{total})")
    if args.require_complete and incomplete:
        raise SystemExit("Incomplete reviews: " + ", ".join(incomplete))


if __name__ == "__main__":
    main()
