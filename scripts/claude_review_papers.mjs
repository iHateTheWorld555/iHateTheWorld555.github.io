#!/usr/bin/env node
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const DEFAULT_SDK_PATH =
  "/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/claude-code-free/node_modules/@anthropic-ai/claude-agent-sdk/sdk.mjs";
const DEFAULT_SKILL_PATH = "/root/.claude/skills/review-paper/SKILL.md";
const DEFAULT_DASHBOARD_CONFIG =
  "/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/claude-tmux-dashboard/config.yaml";

function parseArgs(argv) {
  const opts = {
    date: null,
    scrape: true,
    max: Number(process.env.PAPER_REVIEW_MAX || 0),
    force: false,
    commit: false,
    push: false,
    dryRun: false,
    reviewDir: process.env.PAPER_REVIEW_DIR || "_paper_reviews",
    sdkPath: process.env.CLAUDE_AGENT_SDK_PATH || DEFAULT_SDK_PATH,
    skillPath: process.env.REVIEW_PAPER_SKILL_PATH || DEFAULT_SKILL_PATH,
    dashboardConfig: process.env.CLAUDE_TMUX_DASHBOARD_CONFIG || "",
    claudeCmd: process.env.CLAUDE_REVIEW_CMD || "",
    sdkLauncher: process.env.CLAUDE_REVIEW_SDK_LAUNCHER || "",
    provider: process.env.CLAUDE_REVIEW_PROVIDER || "glm51ascend",
    model: process.env.CLAUDE_REVIEW_MODEL || undefined,
    maxTurns: Number(process.env.CLAUDE_REVIEW_MAX_TURNS || 24),
    maxBudgetUsd: Number(process.env.CLAUDE_REVIEW_MAX_BUDGET_USD || 0),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      i += 1;
      if (i >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[i];
    };

    if (arg === "--date") opts.date = next();
    else if (arg === "--max") opts.max = Number(next());
    else if (arg === "--review-dir") opts.reviewDir = next();
    else if (arg === "--sdk") opts.sdkPath = next();
    else if (arg === "--skill") opts.skillPath = next();
    else if (arg === "--dashboard-config") opts.dashboardConfig = next();
    else if (arg === "--claude-cmd") opts.claudeCmd = next();
    else if (arg === "--sdk-launcher") opts.sdkLauncher = next();
    else if (arg === "--provider") opts.provider = next();
    else if (arg === "--model") opts.model = next();
    else if (arg === "--max-turns") opts.maxTurns = Number(next());
    else if (arg === "--max-budget-usd") opts.maxBudgetUsd = Number(next());
    else if (arg === "--force") opts.force = true;
    else if (arg === "--commit") opts.commit = true;
    else if (arg === "--push") {
      opts.commit = true;
      opts.push = true;
    } else if (arg === "--dry-run") {
      opts.dryRun = true;
      opts.scrape = false;
    } else if (arg === "--no-scrape") opts.scrape = false;
    else if (arg === "--scrape") opts.scrape = true;
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (opts.date !== null && !/^\d{4}-\d{2}-\d{2}$/.test(opts.date)) {
    throw new Error(`Invalid --date: ${opts.date}`);
  }
  if (!Number.isFinite(opts.max) || opts.max < 0) {
    throw new Error("--max must be a non-negative number");
  }
  if (!Number.isFinite(opts.maxTurns) || opts.maxTurns < 1) {
    throw new Error("--max-turns must be a positive number");
  }
  if (!Number.isFinite(opts.maxBudgetUsd) || opts.maxBudgetUsd < 0) {
    throw new Error("--max-budget-usd must be a non-negative number");
  }
  return opts;
}

function printHelp() {
  console.log(`Usage: node scripts/claude_review_papers.mjs [options]

Options:
  --date YYYY-MM-DD        Paper digest date to review (default: newest _papers file)
  --max N                  Review at most N papers; 0 means no limit
  --force                  Re-review papers with existing review files
  --no-scrape              Skip scripts/scrape_papers.py
  --commit                 Commit _papers and review outputs
  --push                   Commit and git push
  --dry-run                Parse and print candidates only
  --sdk PATH               Path to @anthropic-ai/claude-agent-sdk/sdk.mjs
  --skill PATH             Path to review-paper SKILL.md
  --dashboard-config PATH  Path to claude-tmux-dashboard config.yaml
  --claude-cmd PATH        Claude Code launcher (default: dashboard claude_cmd)
  --sdk-launcher PATH      SDK-safe launcher that preserves cwd
  --provider NAME          ccc provider positional argument (default: glm51ascend)
  --model MODEL            Provider-level model override passed before SDK args
  --max-turns N            SDK max turns per paper (default: env or 24)
  --max-budget-usd N       SDK max budget per paper; 0 disables budget cap
`);
}

function parseScalar(raw) {
  const value = String(raw || "").trim();
  if (!value) return "";
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  return value;
}

function parseInlineList(raw) {
  const value = raw.trim();
  if (!value.startsWith("[") || !value.endsWith("]")) return null;
  const inner = value.slice(1, -1).trim();
  if (!inner) return [];
  return inner.split(",").map((item) => parseScalar(item)).filter(Boolean);
}

function loadDashboardConfig(configPath) {
  const candidates = [
    configPath,
    resolve(homedir(), ".claude-tmux-dashboard", "config.yaml"),
    DEFAULT_DASHBOARD_CONFIG,
  ].filter(Boolean);
  const path = candidates.find((candidate) => existsSync(candidate));
  if (!path) return {};

  const cfg = { path, env: {}, add_dirs: [], create_args: [] };
  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  let blockKey = "";

  for (const line of lines) {
    const trimmed = line.replace(/\s+#.*$/, "").trimEnd();
    if (!trimmed.trim() || trimmed.trimStart().startsWith("#")) continue;

    const top = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/);
    if (top) {
      const [, key, raw] = top;
      blockKey = key;
      const inlineList = parseInlineList(raw);
      if (inlineList) cfg[key] = inlineList;
      else if (raw.trim()) cfg[key] = parseScalar(raw);
      else if (key === "env") cfg.env = {};
      else if (key === "add_dirs" || key === "create_args") cfg[key] = [];
      continue;
    }

    const listItem = trimmed.match(/^\s+-\s*(.+)$/);
    if (listItem && Array.isArray(cfg[blockKey])) {
      cfg[blockKey].push(parseScalar(listItem[1]));
      continue;
    }

    const envItem = trimmed.match(/^\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.+)$/);
    if (envItem && blockKey === "env") {
      cfg.env[envItem[1]] = parseScalar(envItem[2]);
    }
  }

  return cfg;
}

function applyClaudeDashboardConfig(opts) {
  const cfg = loadDashboardConfig(opts.dashboardConfig);
  opts.dashboardConfig = cfg.path || opts.dashboardConfig;
  opts.claudeCmd = opts.claudeCmd || cfg.claude_cmd || resolve(dirname(opts.sdkPath), "cli.js");
  opts.sdkLauncher = opts.sdkLauncher || resolve(REPO_ROOT, "scripts", "claude_review_ccc_launcher.sh");
  opts.provider = opts.provider || "glm51ascend";
  opts.createArgs = Array.isArray(cfg.create_args) ? cfg.create_args : [];
  opts.dashboardEnv = cfg.env && typeof cfg.env === "object" ? cfg.env : {};
  opts.dashboardAddDirs = Array.isArray(cfg.add_dirs) ? cfg.add_dirs : [];
}

function run(command, args, opts = {}) {
  console.log(`$ ${[command, ...args].join(" ")}`);
  execFileSync(command, args, {
    cwd: REPO_ROOT,
    stdio: "inherit",
    env: process.env,
    ...opts,
  });
}

function runQuiet(command, args) {
  return spawnSync(command, args, {
    cwd: REPO_ROOT,
    encoding: "utf8",
    env: process.env,
  });
}

function parseDailyPaperFile(date) {
  const file = resolve(REPO_ROOT, "_papers", `${date}.md`);
  if (!existsSync(file)) {
    throw new Error(`Paper file does not exist: ${file}`);
  }

  const content = readFileSync(file, "utf8");
  const sections = content.split(/(?=^## \d+\. )/m).slice(1);
  return sections.map((section) => {
    const header = section.match(/^##\s+(\d+)\.\s+\[(.+?)\]\((https:\/\/arxiv\.org\/abs\/[^)]+)\)/m);
    if (!header) return null;

    const authors = section.match(/\*\*Authors:\*\*\s*(.+)/);
    const categories = section.match(/\*\*Categories:\*\*\s*`(.+?)`/);
    const score = section.match(/\*\*Score:\s*([\d.]+)\/10\*\*/);
    const summary = section.match(/>\s*(.+?)(?:\n---|\n##|\Z)/s);
    const arxivId = header[3].split("/abs/")[1];

    return {
      index: Number(header[1]),
      title: header[2],
      url: header[3],
      arxivId,
      authors: authors?.[1]?.trim() || "",
      categories: categories?.[1]?.trim() || "",
      score: score?.[1] || "",
      summary: summary?.[1]?.replace(/\s+/g, " ").trim() || "",
      section: section.trim(),
    };
  }).filter(Boolean);
}

function latestPaperDate() {
  const papersDir = resolve(REPO_ROOT, "_papers");
  const dates = readdirSync(papersDir)
    .map((name) => name.match(/^(\d{4}-\d{2}-\d{2})\.md$/)?.[1])
    .filter(Boolean)
    .sort();
  if (dates.length === 0) {
    throw new Error(`No daily paper files found in ${papersDir}`);
  }
  return dates[dates.length - 1];
}

function safeFileStem(value) {
  return value.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "");
}

function reviewPathFor(opts, paper) {
  return resolve(REPO_ROOT, opts.reviewDir, opts.date, `${safeFileStem(paper.arxivId)}.md`);
}

function yamlString(value) {
  return JSON.stringify(String(value ?? ""));
}

function buildPrompt(paper, opts) {
  return `/review-paper

请用 review-paper skill 审查下面这篇论文。每篇论文是一次独立会话；不要依赖之前论文的会话上下文。

要求：
- 必须使用 review-paper skill 的七条公理流程。
- 优先读取 arXiv 论文全文；如果只能读到摘要，要在 review 中明确说明。
- 按 skill 要求使用可用的 wiki/paper-wiki/free-search/Read/Bash/Web 工具建立事实锚点。
- 如果某个工具不可用或查询失败，把失败原因写入对应的 Wiki 证据位置，不要假装查过。
- 可以按 skill 要求写入 Wiki，但不要修改当前 git 仓库文件。
- 最终只输出 Step 4 的 Markdown review，不要输出过程日志。

论文信息：
- Title: ${paper.title}
- arXiv ID: ${paper.arxivId}
- URL: ${paper.url}
- Authors: ${paper.authors}
- Categories: ${paper.categories}
- Existing digest score: ${paper.score || "unscored"}

当前 digest 摘要：
${paper.summary}

当前 digest 原始条目：
${paper.section}

Skill path for reference: ${opts.skillPath}
`;
}

function buildSdkOptions(opts) {
  const permissionMode = process.env.CLAUDE_REVIEW_PERMISSION_MODE || "bypassPermissions";
  const executableArgs = [];
  if (opts.provider) executableArgs.push(opts.provider);
  if (opts.model) executableArgs.push("--model", opts.model);
  executableArgs.push("--print");
  executableArgs.push(...(opts.createArgs || []));

  const additionalDirectories = [
    "/root/.claude",
    "/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr",
    ...(opts.dashboardAddDirs || []),
  ].filter((value, index, array) => value && array.indexOf(value) === index);

  return {
    cwd: REPO_ROOT,
    additionalDirectories,
    pathToClaudeCodeExecutable: opts.sdkLauncher,
    executableArgs,
    tools: { type: "preset", preset: "claude_code" },
    disallowedTools: ["Edit", "MultiEdit", "Write", "NotebookEdit"],
    permissionMode,
    allowDangerouslySkipPermissions: permissionMode === "bypassPermissions",
    maxTurns: opts.maxTurns,
    persistSession: true,
    includePartialMessages: false,
    env: {
      ...process.env,
      ...opts.dashboardEnv,
      CLAUDE_AGENT_SDK_CLIENT_APP: "daily-paper-review/1.0",
      CLAUDE_REVIEW_CMD: opts.claudeCmd,
    },
    agents: {
      "paper-reviewer": {
        description: "Strict scientific paper reviewer using the review-paper skill.",
        prompt:
          "You are a strict scientific paper reviewer. Use the preloaded review-paper skill and available research tools to review one paper at a time. Do not edit files in the current repository.",
        skills: ["review-paper"],
        maxTurns: opts.maxTurns,
        permissionMode,
      },
    },
    agent: "paper-reviewer",
    ...(opts.maxBudgetUsd > 0 ? { maxBudgetUsd: opts.maxBudgetUsd } : {}),
  };
}

async function reviewPaper(query, opts, paper) {
  const prompt = buildPrompt(paper, opts);
  const sdkOptions = buildSdkOptions(opts);
  const startedAt = new Date().toISOString();
  const messages = [];
  let result = null;

  console.log(`Reviewing ${paper.index}. ${paper.title}`);
  for await (const message of query({ prompt, options: sdkOptions })) {
    messages.push(message);
    if (message.type === "system" && message.subtype === "init") {
      console.log(`  session: ${message.session_id}`);
    } else if (message.type === "result") {
      result = message;
    }
  }

  if (!result) {
    throw new Error(`No SDK result for ${paper.arxivId}`);
  }
  if (result.subtype !== "success") {
    const errors = result.errors?.join("; ") || result.subtype;
    throw new Error(`Claude review failed for ${paper.arxivId}: ${errors}`);
  }

  const outPath = reviewPathFor(opts, paper);
  mkdirSync(dirname(outPath), { recursive: true });
  const metadata = [
    "---",
    `date: ${opts.date}`,
    `reviewed_at: ${startedAt}`,
    `title: ${yamlString(paper.title)}`,
    `arxiv_id: ${yamlString(paper.arxivId)}`,
    `arxiv_url: ${yamlString(paper.url)}`,
    `daily_index: ${paper.index}`,
    `daily_score: ${yamlString(paper.score)}`,
    `claude_session_id: ${yamlString(result.session_id)}`,
    `claude_turns: ${result.num_turns}`,
    `claude_cost_usd: ${result.total_cost_usd}`,
    "---",
    "",
  ].join("\n");

  writeFileSync(outPath, metadata + result.result.trim() + "\n", "utf8");
  console.log(`  wrote ${outPath}`);
}

function commitAndPush(opts) {
  const paths = ["_papers", opts.reviewDir];
  run("git", ["add", ...paths]);

  const diff = runQuiet("git", ["diff", "--cached", "--quiet"]);
  if (diff.status === 0) {
    console.log("No staged changes to commit.");
    return;
  }

  run("git", ["commit", "-m", `papers: claude reviews ${opts.date}`]);
  if (opts.push) {
    run("git", ["push", "-u", "origin", "HEAD"]);
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));

  if (!existsSync(opts.sdkPath)) {
    throw new Error(`SDK not found: ${opts.sdkPath}`);
  }
  if (!existsSync(opts.skillPath)) {
    throw new Error(`review-paper skill not found: ${opts.skillPath}`);
  }
  applyClaudeDashboardConfig(opts);
  if (!existsSync(opts.claudeCmd)) {
    throw new Error(`Claude Code launcher not found: ${opts.claudeCmd}`);
  }
  if (!existsSync(opts.sdkLauncher)) {
    throw new Error(`SDK launcher not found: ${opts.sdkLauncher}`);
  }

  if (opts.scrape) {
    run("python", ["scripts/scrape_papers.py"]);
  }
  if (opts.date === null) {
    opts.date = latestPaperDate();
  }

  const papers = parseDailyPaperFile(opts.date);
  const candidates = papers.filter((paper) => opts.force || !existsSync(reviewPathFor(opts, paper)));
  const selected = opts.max > 0 ? candidates.slice(0, opts.max) : candidates;

  console.log(`Found ${papers.length} papers for ${opts.date}; ${candidates.length} need review; selected ${selected.length}.`);
  if (opts.dryRun) {
    console.log(`SDK launcher: ${opts.sdkLauncher}`);
    console.log(`Claude launcher: ${opts.claudeCmd}`);
    console.log(`Provider: ${opts.provider || "(none)"}`);
    if (opts.dashboardConfig) console.log(`Dashboard config: ${opts.dashboardConfig}`);
    selected.forEach((paper) => {
      console.log(`${paper.index}. ${paper.arxivId} ${paper.title}`);
    });
    return;
  }
  if (selected.length === 0) {
    if (opts.commit || opts.push) commitAndPush(opts);
    return;
  }

  const { query } = await import(pathToFileURL(opts.sdkPath).href);
  for (const paper of selected) {
    await reviewPaper(query, opts, paper);
  }

  if (opts.commit || opts.push) {
    commitAndPush(opts);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
