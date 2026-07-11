#!/usr/bin/env python3
"""Review daily papers by launching Claude Code directly, without the SDK."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAUNCHER = REPO_ROOT / "scripts" / "claude_review_ccc_launcher.sh"
DEFAULT_SKILLS = [
    "/root/.claude/skills/review-paper",
    "/root/.claude/skills/paper-wiki",
    "/root/.claude/skills/free-search",
    "/root/.claude/skills/tavily-search",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--max", type=int, default=int(os.getenv("PAPER_REVIEW_MAX", "0")))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--scrape", action="store_true", default=True)
    parser.add_argument("--no-scrape", action="store_false", dest="scrape")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--push-branch", default=os.getenv("PAPER_REVIEW_PUSH_BRANCH", "master"))
    parser.add_argument("--review-dir", default=os.getenv("PAPER_REVIEW_DIR", "_paper_reviews"))
    parser.add_argument("--provider", default=os.getenv("CLAUDE_REVIEW_PROVIDER", "glm51ascend"))
    parser.add_argument("--model", default=os.getenv("CLAUDE_REVIEW_MODEL") or None)
    parser.add_argument("--launcher", default=os.getenv("CLAUDE_REVIEW_LAUNCHER", str(DEFAULT_LAUNCHER)))
    parser.add_argument("--config-dir", default=os.getenv("CLAUDE_REVIEW_CONFIG_DIR", str(REPO_ROOT / ".claude-review")))
    parser.add_argument("--max-turns", type=int, default=int(os.getenv("CLAUDE_REVIEW_MAX_TURNS", "40")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("CLAUDE_REVIEW_TIMEOUT_SEC", "1800")))
    args = parser.parse_args()
    if args.push:
        args.commit = True
    return args


def latest_date() -> str:
    dates = sorted(p.stem for p in (REPO_ROOT / "_papers").glob("????-??-??.md"))
    if not dates:
        raise SystemExit("No _papers/YYYY-MM-DD.md files found")
    return dates[-1]


def parse_papers(date: str) -> list[dict]:
    path = REPO_ROOT / "_papers" / f"{date}.md"
    text = path.read_text(encoding="utf-8")
    papers = []
    for section in re.split(r"(?=^## \d+\. )", text, flags=re.M)[1:]:
        header = re.search(r"^##\s+(\d+)\.\s+\[(.+?)\]\((https://arxiv\.org/abs/[^)]+)\)", section, re.M)
        if not header:
            continue
        url = header.group(3)
        summary = re.search(r">\s*(.+?)(?:\n---|\n##|\Z)", section, re.S)
        papers.append(
            {
                "index": int(header.group(1)),
                "title": header.group(2),
                "url": url,
                "arxiv_id": url.rsplit("/abs/", 1)[1],
                "authors": _line(section, "Authors"),
                "categories": _code_line(section, "Categories"),
                "score": _score(section),
                "summary": re.sub(r"\s+", " ", summary.group(1)).strip() if summary else "",
                "section": section.strip(),
            }
        )
    return papers


def _line(text: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _code_line(text: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*`(.+?)`", text)
    return m.group(1).strip() if m else ""


def _score(text: str) -> str:
    m = re.search(r"\*\*Score:\s*([\d.]+/10).*?\*\*", text)
    return m.group(1).strip() if m else ""


def ensure_config_dir(config_dir: Path) -> None:
    skills_dir = config_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    # Enable oh-my-claudecode plugin so wiki_query/wiki_ingest MCP tools are
    # available to the reviewer. OMC provides tools via MCP server only
    # (no SessionStart hooks of its own), so enabling it does not reintroduce
    # the hook-caused hangs that motivated the isolated config in the first
    # place. claude-mem and other plugins stay disabled.
    omc_root = Path("/root/.claude/plugins/marketplaces/oh-my-claudecode")
    (config_dir / "settings.json").write_text(
        json.dumps(
            {
                "enabledPlugins": {
                    "oh-my-claudecode@oh-my-claudecode": True,
                },
                "hooks": {},
                "skipDangerousModePermissionPrompt": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Symlink OMC plugin into the isolated config so the plugin loader finds it.
    plugin_dst = config_dir / "plugins" / "oh-my-claudecode"
    plugin_dst.parent.mkdir(parents=True, exist_ok=True)
    if not plugin_dst.exists() and not plugin_dst.is_symlink():
        plugin_dst.symlink_to(omc_root, target_is_directory=True)
    for raw in DEFAULT_SKILLS:
        src = Path(raw)
        if not src.exists():
            continue
        dst = skills_dir / src.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(src, target_is_directory=True)


def review_path(args: argparse.Namespace, date: str, paper: dict) -> Path:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", paper["arxiv_id"]).strip("_")
    return REPO_ROOT / args.review_dir / date / f"{stem}.md"


def build_prompt(paper: dict) -> str:
    return f"""/review-paper

请用 review-paper skill 严格审查这篇论文。每篇论文是一个全新 Claude Code 进程和全新会话。

要求：
- 按 review-paper skill 的七条公理输出最终 Markdown review。
- 尽量读取 arXiv 论文全文；如果只能读摘要，要明确说明。
- 按 skill 使用可用的 Bash/Read/Web/paper-wiki/free-search 工具建立事实锚点（Step 1-4 必须读 wiki）。
- 如果某个查询或工具失败，直接写失败原因，不要假装查过。
- 不要修改当前 git 仓库文件。
- **跳过 Step 5（wiki_ingest 写回）**：只读 wiki 做研究，不要把 review 写回 wiki。review 直接作为最终 Markdown 输出。
- **打分必须严格基于 7 axiom 判定**，不是凭感觉给分。每条 axiom 0-10 分，按判定映射：
  - ✅ = 8-10 分（公理满足，贡献清晰）
  - ⚠️ = 4-7 分（部分满足，有缺口）
  - ❌ = 0-3 分（不满足，严重缺陷）
  分数要在每条 axiom 的"判定"行后给出。
- **总评末尾输出打分表**，格式严格如下：

```
## 打分

| Axiom | 判定 | 分数 | 权重 | 加权分 |
|-------|------|------|------|--------|
| 一 对象公理 | ✅/⚠️/❌ | X | 1.0 | X |
| 二 识别公理 | ✅/⚠️/❌ | X | 1.5 | X |
| 三 独立性公理 | ✅/⚠️/❌ | X | 1.0 | X |
| 四 压缩公理 | ✅/⚠️/❌ | X | 1.0 | X |
| 五 效用公理 | ✅/⚠️/❌ | X | 2.0 | X |
| 六 新颖性公理 | ✅/⚠️/❌ | X | 2.0 | X |
| 七 可复现公理 | ✅/⚠️/❌ | X | 1.0 | X |

**加权总分: X/10**（加权分之和 / 权重之和 9.5）
**最终建议: <Accept ≥8 / Weak Accept 6.5-8 / Borderline 5-6.5 / Weak Reject 3.5-5 / Reject <3.5>**
```

- 不要再单独给"科学价值/方法价值/社区价值"分数——那些由 7 axiom 打分自然导出。

**关键执行约束（必须严格遵守）**：
- `wiki_query` / `wiki_ingest` 等 OMC wiki MCP 工具**可用**（Step 1-4 必须用 `wiki_query` 查经验知识）。
- 但**禁止 wiki_ingest 写回**（跳过 Step 5）：review 直接作为最终 Markdown 输出，不要调用 `wiki_ingest`。
- `paper-wiki` CLI 也可用：`cd /inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/cc-research/my-paper-wiki && uv run paper-wiki search --concept "..."`。
- **研究阶段（Step 0-3）最多用 15 turns**：读 PDF + wiki_query + paper-wiki + free-search 补充。每个查询失败就记一笔，不要反复重试。
- **Step 4 必须输出完整 review**：研究阶段结束后，立即输出结构化 Markdown review（按 skill 模板：论文类型 → 七条公理审查 → 总评+打分）。
- review 必须是一个完整的 Markdown 文档，以 `# Paper Review:` 开头，以打分结束。不要输出研究过程的叙述，只输出最终 review。

论文信息：
- Title: {paper["title"]}
- arXiv ID: {paper["arxiv_id"]}
- URL: {paper["url"]}
- Authors: {paper["authors"]}
- Categories: {paper["categories"]}
- Digest score: {paper["score"]}

Digest 摘要：
{paper["summary"]}

Digest 原始条目：
{paper["section"]}
"""


def run_review(args: argparse.Namespace, date: str, paper: dict) -> None:
    out_path = review_path(args, date, paper)
    log_path = out_path.with_suffix(".log")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        args.launcher,
        args.provider,
        "--print",
        "--dangerously-skip-permissions",
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(args.max_turns),
        "--setting-sources",
        "user",
        "--permission-mode",
        "bypassPermissions",
        "--allow-dangerously-skip-permissions",
        "--add-dir",
        str(REPO_ROOT),
        "--add-dir",
        "/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr",
    ]
    if args.model:
        cmd[2:2] = ["--model", args.model]
    # Prompt is passed via stdin, not as a positional argument.
    # dev-entry.ts forwards to cli.tsx via commander, where positional prompts
    # after `--` and many flags are unreliable; stdin is the documented --print input.
    prompt_text = build_prompt(paper)

    env = os.environ.copy()
    env.update(
        {
            "IS_SANDBOX": "1",
            "CLAUDE_CONFIG_DIR": str(Path(args.config_dir).resolve()),
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": env.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "198000"),
            "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",
        }
    )

    print(f"Reviewing {paper['index']}. {paper['title']}", flush=True)
    started = time.time()
    session_id = ""
    result_text = ""
    assistant_text_parts: list[str] = []
    result_obj = {}

    with subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:
        try:
            stdout, stderr = proc.communicate(input=prompt_text, timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            stdout, stderr = proc.communicate()
            log_path.write_text(
                (stdout or "") + "\n[stderr]\n" + (stderr or ""),
                encoding="utf-8",
            )
            raise RuntimeError(f"Review timed out after {args.timeout}s; see {log_path}") from exc
        code = proc.returncode

    with log_path.open("w", encoding="utf-8") as log:
        for raw in stdout.splitlines():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.write(f"[stdout] {raw}\n")
                continue
            if msg.get("type") == "system" and msg.get("subtype") == "init":
                session_id = msg.get("session_id", "")
                print(f"  session: {session_id}", flush=True)
            elif msg.get("type") == "assistant":
                text = _assistant_text(msg)
                if text:
                    assistant_text_parts.append(text)
                    print(text[:500], flush=True)
            elif msg.get("type") == "result":
                result_obj = msg
                result_text = msg.get("result") or result_text
            log.write(json.dumps(msg, ensure_ascii=False) + "\n")
        if stderr:
            log.write("\n[stderr]\n")
            log.write(stderr)

    # Fallback: if result.result is empty (e.g. wiki_ingest failure flagged
    # is_error=true), reconstruct review from assistant text chunks.
    if not result_text and assistant_text_parts:
        result_text = "\n".join(assistant_text_parts)
        print(f"  [fallback] reconstructed review from {len(assistant_text_parts)} assistant chunks ({len(result_text)} chars)", flush=True)

    if code != 0 and not result_obj:
        raise RuntimeError(f"Claude Code exited with {code}; see {log_path}")
    if result_obj.get("is_error") and not result_text:
        raise RuntimeError(f"Claude Code result error: {result_obj.get('result')}; see {log_path}")
    if not result_text:
        raise RuntimeError(f"No result text captured; see {log_path}")

    frontmatter = {
        "date": date,
        "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "title": paper["title"],
        "arxiv_id": paper["arxiv_id"],
        "arxiv_url": paper["url"],
        "daily_index": paper["index"],
        "daily_score": paper["score"],
        "claude_session_id": session_id or result_obj.get("session_id", ""),
        "claude_turns": result_obj.get("num_turns", ""),
        "runner": "direct-ccc",
    }
    body = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in frontmatter.items()) + "\n---\n\n"
    out_path.write_text(body + result_text.strip() + "\n", encoding="utf-8")
    print(f"  wrote {out_path}", flush=True)


def _assistant_text(msg: dict) -> str:
    chunks = msg.get("message", {}).get("content", [])
    return "".join(c.get("text", "") for c in chunks if c.get("type") == "text")


def git_commit(args: argparse.Namespace, date: str) -> None:
    subprocess.run(["git", "add", "_papers", args.review_dir], cwd=REPO_ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if diff.returncode == 0:
        print("No staged changes to commit.")
    else:
        subprocess.run(["git", "commit", "-m", f"papers: claude reviews {date}"], cwd=REPO_ROOT, check=True)
    if args.push:
        subprocess.run(
            ["git", "push", "origin", f"HEAD:{args.push_branch}"],
            cwd=REPO_ROOT,
            check=True,
        )


def main() -> None:
    args = parse_args()
    if args.scrape:
        subprocess.run([sys.executable, "scripts/scrape_papers.py"], cwd=REPO_ROOT, check=True)

    date = args.date or latest_date()
    papers = parse_papers(date)
    selected = []
    for paper in papers:
        if not args.force and review_path(args, date, paper).exists():
            continue
        selected.append(paper)
        if args.max and len(selected) >= args.max:
            break

    ensure_config_dir(Path(args.config_dir))
    print(f"Found {len(papers)} papers for {date}; selected {len(selected)}.")
    print(f"Claude config: {Path(args.config_dir).resolve()}")
    print(f"Launcher: {args.launcher}")
    print(f"Provider: {args.provider}")
    if args.dry_run:
        for paper in selected:
            print(f"- {paper['arxiv_id']} {paper['title']}")
        return

    failures = []
    for paper in selected:
        try:
            run_review(args, date, paper)
        except Exception as exc:
            print(f"  [FAIL] {paper['arxiv_id']}: {exc}", flush=True)
            failures.append(paper["arxiv_id"])

    if args.commit:
        git_commit(args, date)
    if failures:
        raise SystemExit(f"{len(failures)} review(s) failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
