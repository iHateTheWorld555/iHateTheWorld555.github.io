#!/usr/bin/env python3
"""Score daily arxiv papers based on research taste axioms.

Uses internal glm5.1-w4a8 API (ccc glm51ascend) for scoring.
Fetches paper HTML from arxiv when available, falls back to abstract.

Six axioms (effect+novelty prioritized):
  A1 — Object (0.1): Real, clearly-defined research object?
  A2 — Identification (0.1): True cause of results identified?
  A3 — Independence (0.1): Evidence independent of pipeline?
  A4 — Compression (0.1): More insight with less complexity?
  A5 — Effectiveness (0.3): Does it outperform prior methods?
  A6 — Novelty (0.3): Is the approach genuinely new?

Usage:
  python scripts/score_papers.py [YYYY-MM-DD]
  # Scores today's papers by default
  # Requires INF_API_KEY environment variable
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO_ROOT / "_papers"

# Internal API config (same as ccc glm51ascend)
INF_API_KEY = os.getenv("INF_API_KEY")
INF_BASE_URL = "https://9obb5eeg99okcgjmhmh8kp5ekqj5ejeh.openapi-sj.sii.edu.cn/v1"
MODEL = "glm5.1-w4a8"

SCORING_PROMPT = """你是一位音频/语音/音乐ML领域的研究品味评审。基于六条科研公理给论文打分。
偏好：效果好的论文、创新的论文给高分；过于拘泥于数学但效果一般的论文不给高分。

## 六公理评分标准

### A1 — 对象公理 (权重0.1)
研究对象是否真实、清晰、独立存在？
- 9-10: 真实清晰的问题，对象可验证
- 7-8: 真实问题，定义合理
- 5-6: 对象存在但模糊或依赖代理指标
- 3-4: 对象可疑或高度依赖代理
- 1-2: 对象模糊/未定义或人为构造

### A2 — 识别公理 (权重0.1)
是否识别了方法有效的原因（因果归因）？
- 9-10: 因果机制清晰，受控验证
- 7-8: 良好消融/隔离，归因基本清楚
- 5-6: 有消融但多混淆因素残留
- 3-4: 消融弱，归因不清
- 1-2: 无消融，只说"它有效"

### A3 — 独立性公理 (权重0.1)
证据是否独立于训练/评测闭环？
- 9-10: 完全独立评测，无循环
- 7-8: 基本独立，小重叠
- 5-6: 有循环依赖（训练/评测重叠）
- 3-4: 显著循环性
- 1-2: 完全循环（同模型生成+评测）

### A4 — 压缩公理 (权重0.1)
是否用更少假设/结构获得了更多可迁移洞察？
- 9-10: 优雅洞察，压缩了理解
- 7-8: 干净方法，贡献清晰
- 5-6: 合理但增量或过度工程
- 3-4: 工程堆叠，缺乏洞察
- 1-2: 纯组合/换名，零压缩增益

### A5 — 效果公理 (权重0.3)
方法效果相比已有方法如何？
- 9-10: 全面碾压先前SOTA，多数指标大幅领先
- 7-8: 某几个核心指标超越先前方法，其余持平
- 5-6: 与先前方法打平，效果过得去但无显著优势
- 3-4: 指标输多赢少，或只与过时基线比较（明明有更新更强基线却选两年前的）
- 1-2: 指标全面被别的方法打爆，或刻意回避公平比较

### A6 — 新颖性公理 (权重0.3)
方法/思路是否新颖？是否与已有工作有本质区别？
- 9-10: 全新范式/视角，开辟新方向，无类似先例
- 7-8: 核心思路新颖，与已有方法有本质区别
- 5-6: 有新元素但主体是已有方法的变体/组合
- 3-4: 换皮/微调，与已有工作区别很小
- 1-2: 几乎是已有方法的复现或简单组合

## 输出格式（仅JSON，不要其他文字）
```json
{
  "a1_object": <1-10>,
  "a2_identification": <1-10>,
  "a3_independence": <1-10>,
  "a4_compression": <1-10>,
  "a5_effectiveness": <1-10>,
  "a6_novelty": <1-10>,
  "total": <加权总分，1位小数>,
  "strengths": "<1-2句核心优势>",
  "weaknesses": "<1-2句核心劣势>"
}
```"""


# Categories that indicate audio/speech/music relevance
AUDIO_CATEGORIES = {"cs.SD", "eess.AS"}
# Keywords that indicate audio relevance in title+abstract
AUDIO_KEYWORDS = re.compile(
    r"\b(audio|speech|voice|sound|acoustic|music|TTS|speaker|vocoder|"
    r"phoneme|prosody|diarization|utterance|spoken|waveform|mel spectrogram|"
    r"singing|codec|deepfake detection|watermark)\b"
    r"|\bASR\b(?!\s*(score|rate|scoring))",
    re.IGNORECASE,
)
# Stricter keywords for title-only matching (avoids "fixed voice" false positives)
TITLE_AUDIO_KEYWORDS = re.compile(
    r"\b(audio|(?<!part-of-)speech|voice|sound|acoustic|music|TTS|ASR|speaker|vocoder|"
    r"phoneme|prosody|diarization|utterance|spoken|waveform|singing|codec)\b",
    re.IGNORECASE,
)
# Exclusion patterns (same as scrape_papers.py)
EXCLUDE_RE = re.compile(
    r"\bdysarthri|\bpatholog|\bclinical\b|\bpatient\b|\bdisease|\bcancer|"
    r"\bcough|\bheart sound|\blung sound|\bdementia\b|\bAlzheimer\b|\bcognitive decline\b|"
    r"\bchild\b|\bpediatric|\binfant\b|\belderly\b|\baging voice|"
    r"\bVietnamese\b|\bGreek\b|\bTamil\b|\bSwahili\b|"
    r"\bIcelandic\b|\bBasque\b|\bMalayalam\b|\bKannada\b|\bTangkhul\b|\bAlgerian\b|"
    r"\bunderwater\b|\bAUV\b|\bmarine\b|\bsonar\b|\broom equalization\b|"
    r"\bloudspeaker\b|\bheadrest\b|\bacoustic attack|\bover-the-air attack|"
    r"\bfraud\b|\bfraud detection\b|"
    r"\bspacecraft\b|\bGNC\b|\bfinitely axiomatiz|\bAFDM\b|\bISAC\b|"
    r"\bvideo codec\b|\blearned video\b|"
    r"\bfacial animation\b|\bface animation\b|\btalking head\b|"
    r"\bjailbreak\b|\brole-play\b|\broleplay\b",
    re.IGNORECASE,
)


def is_audio_paper(sec: str) -> bool:
    """Check if a paper section is relevant to audio/speech/music ML."""
    cats_m = re.search(r"\*\*Categories:\*\*\s*`(.+?)`", sec)
    title_m = re.match(r"## \d+\.\s+\[(.+?)\]", sec)
    title = title_m.group(1) if title_m else ""

    # Check exclusion patterns in title+abstract
    text = title
    summary_m = re.search(r">\s*(.+?)(?:\n---|\n##|\Z)", sec, re.DOTALL)
    if summary_m:
        text += " " + summary_m.group(1)
    if EXCLUDE_RE.search(text):
        return False

    # Core audio categories always pass
    if cats_m:
        cats = cats_m.group(1)
        if any(c in cats for c in AUDIO_CATEGORIES):
            return True

    # Non-core categories: title must contain audio keywords
    # (title is more reliable than abstract for relevance)
    return bool(TITLE_AUDIO_KEYWORDS.search(title))


def parse_paper_markdown(filepath: Path) -> list[dict]:
    """Parse _papers/YYYY-MM-DD.md into list of paper dicts.
    Only returns papers that pass the audio relevance filter."""
    content = filepath.read_text(encoding="utf-8")
    sections = re.split(r"(?=^## \d+\.)", content, flags=re.MULTILINE)
    papers = []
    filtered = 0
    for sec in sections:
        m = re.match(r"## (\d+)\.\s+\[(.+?)\]\((.+?)\)", sec)
        if not m:
            continue
        idx, title, url = int(m.group(1)), m.group(2), m.group(3)

        # Check if already scored
        if re.search(r"\*\*Score:.*?/10\*\*", sec):
            continue

        # Pre-filter: only score audio-relevant papers
        if not is_audio_paper(sec):
            filtered += 1
            continue

        authors_m = re.search(r"\*\*Authors:\*\*\s*(.+)", sec)
        cats_m = re.search(r"\*\*Categories:\*\*\s*`(.+?)`", sec)
        summary_m = re.search(r">\s*(.+?)(?:\n---|\n##|\Z)", sec, re.DOTALL)

        papers.append({
            "idx": idx,
            "title": title,
            "url": url,
            "authors": authors_m.group(1).strip() if authors_m else "",
            "categories": cats_m.group(1).strip() if cats_m else "",
            "summary": summary_m.group(1).strip() if summary_m else "",
        })
    if filtered:
        log.info("Pre-filtered %d non-audio papers (skip scoring)", filtered)
    return papers


def fetch_html_paper(arxiv_url: str) -> str | None:
    """Fetch paper HTML from arxiv if available."""
    # Convert abs URL to HTML URL: arxiv.org/abs/XXXX -> arxiv.org/html/XXXX
    arxiv_id = re.sub(r"v\d+$", "", arxiv_url.split("/abs/")[-1])
    html_url = f"https://arxiv.org/html/{arxiv_id}"

    try:
        client = httpx.Client(timeout=15, follow_redirects=True,
                               headers={"User-Agent": "PaperScoreBot/1.0"})
        resp = client.get(html_url)
        client.close()
        if resp.status_code == 200 and len(resp.text) > 1000:
            # Strip HTML tags, keep text
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()
            # Truncate to ~8000 chars to fit context window
            return text[:8000]
    except Exception:
        pass
    return None


def score_paper(client: httpx.Client, paper: dict, full_text: str | None = None) -> dict | None:
    """Call glm5.1-w4a8 to score one paper."""
    # Build content: prefer full text, fall back to abstract
    if full_text:
        paper_content = f"Title: {paper['title']}\nAuthors: {paper['authors']}\nCategories: {paper['categories']}\n\nFull paper text (truncated):\n{full_text}"
    else:
        paper_content = f"Title: {paper['title']}\nAuthors: {paper['authors']}\nCategories: {paper['categories']}\nAbstract: {paper['summary']}"

    prompt = f"{SCORING_PROMPT}\n\n论文内容：\n{paper_content}\n\n打分。仅输出JSON。"

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 16384,
    }
    headers = {
        "Authorization": f"Bearer {INF_API_KEY}",
        "Content-Type": "application/json",
    }

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.post(f"{INF_BASE_URL}/chat/completions", json=body, headers=headers, timeout=180)
            if resp.status_code in (429, 502, 503, 504) and attempt < max_retries:
                wait = min(30 * attempt, 120)
                log.warning("API %d for %s, attempt %d/%d, wait %ds",
                            resp.status_code, paper["title"][:40], attempt, max_retries, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            log.warning("No JSON in response for: %s", paper["title"][:60])
            return None
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt >= max_retries:
                log.warning("Scoring failed after %d retries for %s: %s", max_retries, paper["title"][:40], exc)
                return None
            wait = min(30 * attempt, 120)
            log.warning("Timeout for %s, attempt %d/%d, wait %ds", paper["title"][:40], attempt, max_retries, wait)
            time.sleep(wait)
            continue
        except Exception as exc:
            log.warning("Scoring failed for %s: %s", paper["title"][:60], exc)
            return None
    return None


def rewrite_paper_file(filepath: Path, papers: list[dict], scores: dict[int, dict]):
    """Rewrite markdown file with scores inserted and papers reordered by score."""
    content = filepath.read_text(encoding="utf-8")

    # Insert score blocks
    for paper in papers:
        score = scores.get(paper["idx"])
        if not score:
            continue
        score_block = (
            f"\n**Score: {score['total']}/10** "
            f"(Obj:{score['a1_object']} Id:{score['a2_identification']} "
            f"Ind:{score['a3_independence']} Comp:{score['a4_compression']} "
            f"Eff:{score['a5_effectiveness']} Nov:{score.get('a6_novelty', '-')})\n"
            f"- **Strength:** {score['strengths']}\n"
            f"- **Weakness:** {score['weaknesses']}\n"
        )
        # Insert after the categories line (and optional comment line)
        pattern = rf"(## {paper['idx']}\.\s+\[{re.escape(paper['title'])}\].*?\*\*Categories:\*\*\s*`.+?`[^\n]*(?:\n\s+\|.+?[^\n]*)?)"
        m = re.search(pattern, content, re.DOTALL)
        if m:
            content = content[:m.end()] + score_block + content[m.end():]

    # Reorder by score (descending) and renumber
    content = reorder_by_score(content)
    filepath.write_text(content, encoding="utf-8")


def reorder_by_score(content: str) -> str:
    """Parse scored markdown, filter non-audio, reorder by score descending, renumber."""
    # Split front matter and body
    fm_match = re.match(r"(---\n.*?\n---\n+)(.*)", content, re.DOTALL)
    if not fm_match:
        return content
    front_matter, body = fm_match.group(1), fm_match.group(2)

    # Split into paper sections
    sections = re.split(r"(?=^## \d+\.)", body, flags=re.MULTILINE)
    header = sections[0]  # "# Daily Papers — ..." line
    paper_sections = sections[1:]

    # Filter non-audio papers
    audio_sections = []
    removed = 0
    for sec in paper_sections:
        if is_audio_paper(sec):
            audio_sections.append(sec)
        else:
            removed += 1
            title_m = re.match(r"## \d+\.\s+\[(.+?)\]", sec)
            log.info("Filtered non-audio: %s", title_m.group(1)[:60] if title_m else "unknown")
    if removed:
        log.info("Filtered out %d non-audio papers", removed)

    # Extract score from each section and sort
    scored_sections = []
    unscored_sections = []
    for sec in audio_sections:
        score_m = re.search(r"\*\*Score:\s*([\d.]+)/10\*\*", sec)
        if score_m:
            total = float(score_m.group(1))
            scored_sections.append((total, sec))
        else:
            unscored_sections.append((0, sec))

    # Sort: scored by total descending, then unscored
    all_sections = sorted(scored_sections, key=lambda x: x[0], reverse=True) + unscored_sections

    # Renumber
    result = front_matter + header
    for new_idx, (_, sec) in enumerate(all_sections, 1):
        sec = re.sub(r"^## \d+\.", f"## {new_idx}.", sec, count=1, flags=re.MULTILINE)
        result += sec

    # Update paper count in header
    total_count = len(all_sections)
    result = re.sub(r"\*\*\d+ papers\*\*", f"**{total_count} papers**", result, count=1)

    # Update front matter stats (add if missing, update if present)
    scored_list = [s[0] for s in scored_sections]
    if scored_list:
        avg = sum(scored_list) / len(scored_list)
        top = max(scored_list)
        stats_line = f"avg_score: {avg:.1f}\ntop_score: {top:.1f}\npapers_scored: {len(scored_list)}\n"
        # Remove existing stats lines
        result = re.sub(r"avg_score: .*\n", "", result)
        result = re.sub(r"top_score: .*\n", "", result)
        result = re.sub(r"papers_scored: .*\n", "", result)
        # Insert before closing front matter
        result = re.sub(r"---\n\n# Daily", stats_line + "---\n\n# Daily", result, count=1)

    return result


def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    filepath = PAPERS_DIR / f"{target_date}.md"

    if not filepath.exists():
        log.error("No paper file for %s", target_date)
        sys.exit(1)

    if not INF_API_KEY:
        log.error("INF_API_KEY not set (required for scoring)")
        sys.exit(1)

    papers = parse_paper_markdown(filepath)
    log.info("Found %d unscored papers for %s", len(papers), target_date)

    if not papers:
        log.info("All papers already scored or none found")
        sys.exit(0)

    # Create httpx client for internal API
    client = httpx.Client(timeout=180, follow_redirects=True)

    scores = {}
    for i, paper in enumerate(papers):
        log.info("Scoring %d/%d: %s", i + 1, len(papers), paper["title"][:60])

        # Try fetching HTML version
        full_text = fetch_html_paper(paper["url"])
        if full_text:
            log.info("  Got HTML version (%d chars)", len(full_text))
        else:
            log.info("  Using abstract only")

        score = score_paper(client, paper, full_text)
        if score:
            # Compute weighted total
            total = (
                score.get("a1_object", 5) * 0.1
                + score.get("a2_identification", 5) * 0.1
                + score.get("a3_independence", 5) * 0.1
                + score.get("a4_compression", 5) * 0.1
                + score.get("a5_effectiveness", 5) * 0.4
                + score.get("a6_novelty", 5) * 0.2
            )
            score["total"] = round(total, 1)
            scores[paper["idx"]] = score
            log.info("  Score: %.1f (A1:%d A2:%d A3:%d A4:%d A5:%d A6:%d)",
                     total, score["a1_object"], score["a2_identification"],
                     score["a3_independence"], score["a4_compression"],
                     score["a5_effectiveness"], score.get("a6_novelty", 0))
        else:
            log.warning("  Failed to score")

        time.sleep(2)  # rate limit for internal API

    client.close()

    log.info("Scored %d/%d papers", len(scores), len(papers))

    if scores:
        rewrite_paper_file(filepath, papers, scores)
        log.info("Written scores to %s", filepath)


if __name__ == "__main__":
    main()
