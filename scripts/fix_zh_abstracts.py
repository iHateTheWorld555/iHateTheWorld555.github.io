#!/usr/bin/env python3
"""Re-generate corrupted Chinese abstracts by fetching full abstract from arXiv."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "claude_review_ccc_launcher.sh"
CONFIG_DIR = REPO_ROOT / ".claude-review"
PAPERS_DIR = REPO_ROOT / "_papers"

BAD_PATTERNS = [
    "英文摘要不完整", "让我尝试", "让我查找", "让我搜索", "我来尝试", "让我来",
    "让我翻译", "我来概括", "让我总结", "我需要", "我来写", "让我写",
    "我无法", "无法获取", "无法访问", "摘要不完整", "完整摘要",
    "用户希望我", "用户想让我", "用户要求", "要写准确的中文摘要",
    "需要先看到", "我用 WebFetch", "我使用", "我来为", "我去 arXiv",
    "我尝试", "我直接根据", "基于您提供", "如需更精确",
]


def is_bad(zh: str) -> bool:
    return any(p in zh for p in BAD_PATTERNS)


def fetch_full_abstract(arxiv_url: str) -> str:
    arxiv_id = arxiv_url.rsplit("/abs/", 1)[1]
    api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        resp = httpx.get(api_url, timeout=30, headers={"User-Agent": "AudioPaperDigestBot/1.0"})
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        NS = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", NS)
        if entry is None:
            return ""
        summary = entry.find("atom:summary", NS)
        if summary is None or not summary.text:
            return ""
        return re.sub(r"\s+", " ", summary.text).strip()
    except Exception:
        return ""


def gen_zh(title: str, abstract: str) -> str:
    prompt = (
        f"请用中文写一段3-5句的摘要，概括这篇arXiv论文的核心问题、方法和主要结果。"
        f"只输出中文摘要正文，不要加任何前缀、不要加标题、不要解释你在做什么、"
        f"不要提到用户、摘要、翻译等元话语。直接输出摘要内容。\n\n"
        f"标题：{title}\n英文摘要：{abstract}"
    )
    cmd = [
        str(LAUNCHER), "glm52", "--print", "--dangerously-skip-permissions",
        "--output-format", "stream-json", "--verbose", "--max-turns", "3",
        "--setting-sources", "user", "--permission-mode", "bypassPermissions",
        "--allow-dangerously-skip-permissions",
    ]
    env = os.environ.copy()
    env.update({
        "IS_SANDBOX": "1",
        "CLAUDE_CONFIG_DIR": str(CONFIG_DIR.resolve()),
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "64000",
    })
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=120, cwd=REPO_ROOT, env=env,
        )
    except subprocess.TimeoutExpired:
        return ""
    last_assistant = ""
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "result" and msg.get("result", "").strip():
            return msg["result"].strip()
        if msg.get("type") == "assistant":
            t = "".join(
                c.get("text", "") for c in msg.get("message", {}).get("content", [])
                if c.get("type") == "text"
            ).strip()
            if t:
                last_assistant = t
    return last_assistant


def find_bad_papers() -> list[tuple[Path, str, str, str, str]]:
    """Return (file, title, url, old_zh_line, section_text)."""
    results = []
    for f in sorted(PAPERS_DIR.glob("????-??-??.md")):
        text = f.read_text("utf-8")
        for section in re.split(r"(?=^## \d+\. )", text, flags=re.M)[1:]:
            header = re.search(r"^##\s+\d+\.\s+\[(.+?)\]\((https://arxiv\.org/abs/[^)]+)\)", section, re.M)
            if not header:
                continue
            zh_m = re.search(r"(> \*\*中文摘要[：:]\*\*\s*)(.+?)(?:\n\n|\n>|\Z)", section, re.S)
            if not zh_m:
                continue
            zh = zh_m.group(2).strip()
            if is_bad(zh):
                results.append((f, header.group(1), header.group(2), zh_m.group(0), section))
    return results


def replace_zh(file: Path, old_line: str, new_zh: str) -> None:
    text = file.read_text("utf-8")
    new_line = f"> **中文摘要：** {new_zh}"
    text = text.replace(old_line, new_line, 1)
    file.write_text(text, "utf-8")


def main() -> None:
    bad = find_bad_papers()
    print(f"Found {len(bad)} corrupted abstracts")
    for i, (file, title, url, old_line, section) in enumerate(bad, 1):
        print(f"\n[{i}/{len(bad)}] {title[:60]}", flush=True)
        print(f"  fetching full abstract from arXiv...", flush=True)
        abstract = fetch_full_abstract(url)
        if not abstract:
            # fallback: use existing English abstract from section
            en_m = re.search(r"^>\s*(.+?)(?:\n---|\n##|\Z)", section, re.M | re.S)
            abstract = re.sub(r"\s+", " ", en_m.group(1)).strip() if en_m else ""
        if not abstract:
            print("  [FAIL] no abstract", flush=True)
            continue
        print(f"  abstract: {abstract[:80]}...", flush=True)
        zh = gen_zh(title, abstract)
        if zh and not is_bad(zh):
            replace_zh(file, old_line, zh)
            print(f"  fixed: {zh[:80]}...", flush=True)
        else:
            print(f"  [FAIL] bad output: {zh[:80] if zh else 'empty'}", flush=True)
        time.sleep(1)
    print("\nDone")


if __name__ == "__main__":
    main()
