# news-reader

本地新闻阅读器（Web 版），数据源来自 `DailyNews`，用于新闻流扫读、稍后阅读、想法沉淀、提醒、跟踪主题与复盘。

当前稳定版本：`v2.1.2.2`。版本更新历史见 [CHANGELOG.md](CHANGELOG.md)。

## 核心能力

- **DailyNews 增量索引**：扫描 `dailyFreshNews_*.md` 作为输入锚点；同名 `.newsreader.json` sidecar 存在且合法时优先使用 JSON，缺失或解析失败时回退 Markdown。
- **三栏工作台**：左侧集合/筛选，中栏新闻列表，右栏详情与工具区；移动端使用单栏与底部 Tab。
- **阅读状态管理**：支持已读/未读、重要、稍后再看、收藏、来源筛选、日期分组与阅读断点。
- **新闻流二级信源开关**：可按 Reuters 栏目、X/Twitter 账号等二级来源关闭新闻流显示；不修改已读状态，恢复后未读新闻重新出现。
- **稍后阅读正文抓取**：后台任务通过 opencli 适配器抓取 Reuters、Bloomberg、TechCrunch、Ars、Twitter/X 等正文，写入本地缓存；非 Twitter/X 正文可继续生成中文内容。
- **研究工作流**：支持新闻想法、板块想法、独立想法、市场方向标签、提醒、跟踪主题与版本化复盘。
- **LLM / Chat 集成**：DeepSeek、OpenAI/Codex、Pi 等能力按本地配置、Keychain 密钥和 CLI 可用性启用。

## 输入数据口径

- 默认新闻输入目录由 `settings.py` 的 `DAILY_NEWS_DIR` 定义，可用 `NEWS_READER_DAILY_NEWS_DIR` 覆盖。
- 扫描入口始终是 Markdown 文件：`dailyFreshNews_*.md`。
- 若同目录存在同名 sidecar JSON（如 `dailyFreshNews_2026-07-28.newsreader.json`）且结构合法，解析器优先使用 JSON 中的结构化字段。
- 若 sidecar JSON 不存在、为空、格式非法或字段不完整，解析器回退到 Markdown 正文解析，保证旧数据仍可读。
- 运行数据写入本地 SQLite 与缓存目录，不写回 DailyNews 原始 Markdown。

## 项目结构

- `app.py`：Flask Web/API 服务与后台任务入口。
- `parser.py`：DailyNews Markdown / sidecar JSON 解析。
- `scanner.py`：增量扫描、去重与索引更新。
- `settings.py`：本地路径、数据库与应用设置默认值。
- `daily_briefings.py`：日报/briefing 数据处理。
- `llm_client.py`：LLM 客户端封装。
- `secret_store.py`：Keychain 密钥读取。
- `schema.sql`：SQLite schema。
- `static/`：前端页面、脚本、样式与来源图标。
- `tests/`：pytest 测试。
- `scripts/start-tailscale.sh`：Tailscale 辅助启动脚本。
- `CHANGELOG.md`：版本更新历史。

## 安装要求

- Python 3.10+。
- 依赖安装：`python3 -m pip install -r requirements.txt`。
- 可选：本地安装并登录 `opencli`，用于正文抓取、LLM/Chat 等外部能力。
- 可选：Tailscale，用于局域网/远程访问本机服务。

## 运行方式

```bash
cd /Users/x/news-reader/news-reader
python3 app.py
```

可通过以下环境变量覆盖本地路径与监听参数：

- `NEWS_READER_HOST`：覆盖监听 host。
- `NEWS_READER_PORT`：覆盖监听 port。
- `NEWS_READER_DB_PATH`：覆盖 SQLite 数据库路径。
- `NEWS_READER_DAILY_NEWS_DIR`：覆盖 DailyNews 输入目录。
- `NEWS_READER_DAILY_BRIEFING_DIR`：覆盖 Daily Briefing 输入目录。
- `NEWS_READER_APP_SETTINGS_PATH`：覆盖应用运行设置文件路径。
- `NEWS_READER_MEDIA_CACHE_DIR`：覆盖媒体缓存目录。

访问地址取决于 host/port；本机常用形式为 `http://127.0.0.1:<port>`。

## Tailscale

本机访问可配合 Tailscale 使用。项目内保留辅助脚本：

```bash
cd /Users/x/news-reader/news-reader
scripts/start-tailscale.sh
```

脚本会先读取终端环境变量 `DEEPSEEK_API_KEY`；若不存在，再从 macOS Keychain 的 `DEEPSEEK_API_KEY` service 读取；两者都没有时会报错退出。密钥满足后，脚本会读取/校验 Tailscale IPv4，使用该 IP 绑定 `NEWS_READER_HOST`，并直接执行 `python3 app.py` 启动 news-reader；运行脚本后无需再单独启动服务。

## 配置与 Keychain

敏感密钥不写入仓库。DeepSeek 等密钥通过 macOS Keychain 读取，例如：

```bash
security add-generic-password -a news-reader -s DEEPSEEK_API_KEY -w '你的 DeepSeek API Key' -U
```

运行时读取逻辑见 `secret_store.py` 与 `llm_client.py`。如果本地未配置对应密钥或 CLI，相关 AI 功能应显示为不可用或降级，不影响基础新闻阅读。

## 测试

```bash
cd /Users/x/news-reader/news-reader
PYTHONPATH=. python3 -m pytest -q
```

按改动范围追加轻量检查：

```bash
node --check static/app.js
python3 -m py_compile app.py parser.py scanner.py llm_client.py secret_store.py settings.py daily_briefings.py
git diff --check
```

纯文档改动通常至少运行 `git diff --check`。

## 运行数据与 Git 边界

- 仓库只提交源代码、静态资源、测试、schema、脚本和文档。
- 本地运行数据不得提交，包括 `news_index.sqlite3`、`news_reader.db`、`media-cache/`、SQLite `*.sqlite3*` / `*.db*` 临时文件等。
- `.gitignore` 若存在用户本地脏改，除非任务明确要求，否则不得顺手纳入提交。
- release notes 统一更新 [CHANGELOG.md](CHANGELOG.md)，不要再把完整版本历史追加到 README。
