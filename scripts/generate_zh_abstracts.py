#!/usr/bin/env python3
"""Generate Chinese abstracts for papers in _papers/*.md via Claude Code (glm52)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "claude_review_ccc_launcher.sh"
CONFIG_DIR = REPO_ROOT / ".claude-review"
PAPERS_DIR = REPO_ROOT / "_papers"


def parse_papers(md_path: Path) -> list[dict]:
    text = md_path.read_text("utf-8")
    papers = []
    for section in re.split(r"(?=^## \d+\. )", text, flags=re.M)[1:]:
        header = re.search(r"^##\s+\d+\.\s+\[(.+?)\]\((https://arxiv\.org/abs/[^)]+)\)", section, re.M)
        if not header:
            continue
        title = header.group(1)
        url = header.group(2)
        m = re.search(r"^>\s*(.+?)(?:\n---|\n##|\Z)", section, re.M | re.S)
        abstract = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        has_zh = "**中文摘要：**" in section or "**中文摘要:**" in section
        papers.append({
            "title": title,
            "url": url,
            "abstract": abstract,
            "section": section,
            "has_zh": has_zh,
        })
    return papers


def gen_zh(title: str, abstract: str) -> str:
    prompt = (
        f"请用中文写一段3-5句的摘要，概括这篇arXiv论文的核心问题、方法和主要结果。"
        f"只输出中文摘要正文，不要加任何前缀或标题，输出为一段连续文本。\n\n"
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


def inject_zh(md_path: Path, papers: list[dict], zh_map: dict) -> None:
    text = md_path.read_text("utf-8")
    for p in papers:
        zh = zh_map.get(p["url"])
        if not zh:
            continue
        old = p["section"]
        en_m = re.search(r"(^>.*(?:\n>.*)*)", old, re.M)
        if not en_m:
            continue
        zh_block = f"\n> **中文摘要：** {zh}\n"
        new = old[:en_m.start()] + zh_block + "\n" + old[en_m.start():]
        text = text.replace(old, new, 1)
    md_path.write_text(text, "utf-8")


def main() -> None:
    total = 0
    done = 0
    for md in sorted(PAPERS_DIR.glob("????-??-??.md")):
        papers = parse_papers(md)
        todo = [p for p in papers if not p["has_zh"]]
        if not todo:
            print(f"{md.name}: skip (all have zh)")
            continue
        print(f"\n=== {md.name}: {len(todo)} papers need zh abstract ===", flush=True)
        total += len(todo)
        zh_map = {}
        for i, p in enumerate(todo, 1):
            print(f"  [{i}/{len(todo)}] {p['title'][:60]}", flush=True)
            zh = gen_zh(p["title"], p["abstract"])
            if zh:
                zh_map[p["url"]] = zh
                done += 1
            else:
                print(f"    [FAIL]", flush=True)
            time.sleep(0.3)
        if zh_map:
            inject_zh(md, papers, zh_map)
            print(f"  injected {len(zh_map)} into {md.name}", flush=True)
    print(f"\nDone: {done}/{total} zh abstracts generated")


if __name__ == "__main__":
    main()
