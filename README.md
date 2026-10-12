# news-reader

本地新闻阅读器（Web 版），数据源来自 `DailyNews`，用于新闻流扫读、稍后阅读、想法沉淀、提醒、跟踪主题与复盘。

当前稳定版本：`v2.3.1.1`。版本更新历史见 [CHANGELOG.md](CHANGELOG.md)。

## 核心能力

- **DailyNews 增量索引**：扫描 `dailyFreshNews_*.md` 作为输入锚点；同名 `.newsreader.json` sidecar 存在且合法时优先使用 JSON，缺失或解析失败时回退 Markdown。
- **三栏工作台**：左侧集合/筛选，中栏新闻列表，右栏详情与工具区；移动端使用单栏与底部 Tab。
- **新闻展示规则**：中栏与右栏新闻标题最多显示 5 行；Bloomberg 独立 Video 页面不进入新闻流、搜索、集合或趋势新闻入口。
- **阅读状态管理**：支持已读/未读、重要、稍后再看、收藏、来源筛选、日期分组与阅读断点。
- **新闻流二级信源开关**：可按 Reuters 栏目、X/Twitter 账号等二级来源关闭新闻流显示；不修改已读状态，恢复后未读新闻重新出现。
- **稍后阅读正文抓取**：后台任务通过 opencli 适配器抓取 Reuters、Bloomberg、TechCrunch、Ars、Twitter/X 等正文，写入本地缓存；非 Twitter/X 正文可继续生成中文内容。
- **研究工作流**：支持新闻想法、板块想法、独立想法、市场方向标签、提醒、跟踪主题与版本化复盘。
- **复盘自动续期**：已到期复盘保存“记录进展”后，下一次计划自动设为记录当天后的 15 个自然日，并同步移动严格匹配的有效复盘提醒；未到期复盘、其它提醒和无关联提醒保持不变。
- **正文内新闻研究 Agent**：每篇新闻使用独立短期原文快照会话；右栏右下角悬浮按钮可打开半栏浮窗，并可放大至整栏，正文滚动和聊天互不重排；桌面端首次展开默认使用右栏可用内容区的 2/3，可从顶部拖拽调整并记住高度，放大后还原到已保存高度，手机端不启用拖拽；支持划线引用提问、后台异步任务、SSE 重连、停止/重试、服务重启恢复提示，以及切换新闻后的继续运行。“新会话”会物理删除本篇旧临时数据后重新开始；设置页仍可清空全部临时会话。已有 Agent 回答且没有运行中的任务时，可将当前可见问答归档为中文结论并追加到本篇“我的想法”，成功后同步详情与列表预览；长英文、URL、代码行和引用会在悬浮窗消息宽度内断行，聊天区域保持纵向滚动。
- **LLM / Chat 集成**：DeepSeek 负责新闻翻译与结构化中文内容，新闻 Chat、归档和研究 Agent 以 OAR/Pi SDK 为主，旧同步会话及不受信任项目保留 Pi CLI 兼容路径。保留模型选择、扩展、工具、skills、新闻上下文与连续对话；归档使用独立任务。Agent 不保证只读，不能把可执行工具当成沙箱。

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
- 可选：本地安装并登录 `opencli`，用于正文抓取等外部能力。
- 新闻 Chat / Agent：Node.js **24+**，在项目目录运行 `npm ci --ignore-scripts`。OAR 固定为 `0.52.0`、Pi SDK / Pi AI 固定为 `1.1.0`，安装按 `package-lock.json`，不会在启动时自动安装或升级。无需单独启动 OAR 服务。
- Pi 的模型目录展示仍使用本机 `pi --list-models`；请保留 Pi CLI 安装，并自行配置所选模型的可用凭据。未配置凭据或本机联网扩展所需服务不可用时，应用会报告失败，不替用户登录或启动服务。
- 可选：Tailscale，用于局域网/远程访问本机服务。

## 运行方式

macOS 日常使用推荐在 Finder 中双击项目根目录的 `启动NewsReader.command`。它会先检查 Flask / OpenAI 等 Python 运行依赖；若缺少依赖，会直接给出可复制的 `pip install -r requirements.txt` 命令，不会误报为服务健康检查失败。依赖满足后，它以项目目录为工作目录启动受控 supervisor，确认本次启动的服务实例及静态资源健康后才打开浏览器。若未显式设置 `NEWS_READER_HOST` 且本机已安装并连接 Tailscale，会自动使用 Tailscale IPv4 监听；未检测到可用地址时回退到 `127.0.0.1`。默认访问地址（无可用 Tailscale 时）为 `http://127.0.0.1:8080`。终端中也可运行：

```bash
cd /Users/x/news-reader/news-reader
./启动NewsReader.command
# 等价的受控命令行入口
python3 updater.py --serve
```

受控入口保留 `NEWS_READER_HOST` / `NEWS_READER_PORT` 覆盖，例如：

```bash
NEWS_READER_HOST=localhost NEWS_READER_PORT=8081 ./启动NewsReader.command
```

同一项目再次双击会复用并打开由该 supervisor 管理、且通过本次实例标识健康校验的服务，不会再启动第二个服务。若端口被其它进程占用，启动会明确失败，不会仅凭旧服务仍可响应就误判为本次启动成功。关闭启动终端或发送中断/终止信号时，supervisor 只清理由自身启动的服务进程组；若更新正在进行，会等更新成功或安全回退后再退出。

仍可直接运行不受控入口：

```bash
cd /Users/x/news-reader/news-reader
python3 app.py
```

直接运行 `app.py` 不启用受控更新；设置页确认更新会返回 `managed_launcher_required`，不会改动 Git。可通过以下环境变量覆盖本地路径与监听参数：

- `NEWS_READER_HOST`：覆盖监听 host。
- `NEWS_READER_PORT`：覆盖监听 port。
- `NEWS_READER_DB_PATH`：覆盖 SQLite 数据库路径。未设置时，若项目父目录已有历史 `news_index.sqlite3`，优先继续使用该数据库；否则使用项目目录下的 `news_index.sqlite3`。
- `NEWS_READER_DAILY_NEWS_DIR`：覆盖 DailyNews 输入目录。
- `NEWS_READER_DAILY_BRIEFING_DIR`：覆盖 Daily Briefing 输入目录。
- `NEWS_READER_APP_SETTINGS_PATH`：覆盖应用运行设置文件路径。
- `NEWS_READER_MEDIA_CACHE_DIR`：覆盖媒体缓存目录。
- `NEWS_READER_AGENT_DB_PATH`：覆盖新闻研究 Agent 独立临时 SQLite 路径；默认与主数据库同目录，文件不进入 Git 或常规新闻库备份。
- `NEWS_READER_AGENT_RUNTIME_DIR`：覆盖 OAR/Pi/Codex 研究会话映射临时目录；默认位于系统临时目录并按会话 TTL 清理。

- `NEWS_READER_NODE`：指定用于 OAR 的 Node 可执行文件；默认从 PATH 寻找。
- `NEWS_READER_PI_AGENT_DIR`：指定只读来源 Pi 配置目录；否则使用 `PI_CODING_AGENT_DIR`，最后回退到 `~/.pi/agent`。

### Codex 新闻 Chat（v2.3.1.1）

设置 → Chat 与新闻研究 Agent，先选 Pi 或 Codex，再配置所选运行方式的 provider/model；缺省仍为 Pi，不适用的选项隐藏并禁用。两套配置分别保留，切换只影响新会话。已有对话的 runtime、模型选择、profile 名称与文件沙盒策略保持不变，续问/重试不把 Pi 会话 ID 传给 Codex，也不反向迁移；需要切换时明确点击“新会话”。DeepSeek 翻译、固定总结和 Pi 兼容模式不变。

先在本机安装并配置 Codex CLI；原生 OpenAI provider 的登录与自定义/本地 provider 的认证由 Codex 管理。应用只把 `codex login status` 作为 OpenAI 登录提示，不据此阻止调用或要求重新登录，不读取、复制或存储账号凭据。`NEWS_READER_CODEX` 可指定可执行文件，否则从 PATH 寻找 `codex`。本轮按 Codex CLI 0.158.0 的 `exec --json` / `exec resume` 协议适配，启动前检查命令能力；缺少或不兼容的命令会阻止启动；状态探测失败不等同于认证失败，真正执行返回的认证错误才提示检查所选 provider/profile。不自动改走 Pi。

Codex provider 和模型可留空使用本机 CLI 配置，也可填写已配置的 provider 名称及明确模型；profile 是本机已有名称。应用与启动终端都继承 PATH、HOME 和 CODEX_HOME，不自行切换用户或配置目录。**冻结的是显式 provider/model/profile 选择，不复制本机 profile 内容；留空模型的实际默认值及 profile 内工具/网络配置仍由本机 Codex 管理，外部修改可能影响续问。**若需要模型稳定，请填写明确模型名。每次调用显式固定项目目录、`read-only` 文件沙盒与 `approval_policy=never`；不添加目录、不绕过沙盒、不自动扩大项目信任。文件沙盒不意味着 MCP、hooks 或远程工具全部只读，这些仍需由用户按本机原有权限管理。新闻资料不作为改变权限的指令；联网是否可用须实际验证。

后台任务保留原有流式状态、停止与重试。只有非空最终答案、完整终态、正常退出和应用会话映射保存成功才判成功；未知/重复/缺失事件不以先前片段补成成功。停止后先回收进程组，再允许同会话重试。归档使用独立的临时 Codex 调用，不续接聊天线程；失败或空结果不改笔记。原生 Codex 历史由 CLI 管理，应用只保存私有映射；清空应用会话不会主动删除本机 Codex 全局历史，CLI 账号/历史维护仍由用户负责。

### OAR 会话兼容与边界

Python 后端通过标准输入/JSONL 输出调用短生命周期 Node 桥接，不另开端口。只有收到明确、完整的完成结果才显示成功；超时、取消、异常退出和残缺输出可重试。原生 OAR 会话保存于应用独立临时目录；切页不取消任务，重新打开仍从任务数据库恢复进度与消息。

旧后台 Agent 聊天记录保留，首次续问携带应用保存的可见历史建立当前执行路径的新会话；界面会解释这种接续不包含迁移前工具状态，之后原生续接。旧同步 Chat 接口可将原 Pi 会话文件复制到应用临时区，保留 Pi CLI 原生续接；找不到时明确报错，不静默新建空会话。新会话/TTL 清理仍按原有规则执行。归档有独立会话，结束后清理，不污染聊天。

为避免 OAR 自动写入信任信息或刷新凭据时修改真实账号配置，每轮复制 Pi 配置与资源到权限受限的临时目录，结束或停止后删除凭据副本，只保留应用会话；不会把刷新结果写回真实 Pi 账号。扩展的外部依赖仍需用户自行满足，例如现有 `@ollama/pi-web-search` 要求本机 Ollama 服务可访问。配置中相对路径、可写资源及外部扩展的行为需要在升级后实际核对，不能仅凭普通问答宣称联网等价。

**权限提示**：桥接在运行前按固定 Pi SDK 版本的非交互 CLI 规则核对项目信任（全局信任扩展、已有信任记录及默认策略），不自动扩大权限。若原规则不允许加载项目资源或信任信息无法核实，则走 Pi CLI 原生兼容路径，保留全局工具和原有信任行为，不代替用户授权。会话绑定执行方式，续问和重试不混用 CLI/OAR 会话 ID；已有 OAR 会话的信任改变时明确报错，需检查信任或明确新建会话。OAR 上游仍会写信任记录，但只有原规则已允许或根本没有受信任约束的项目资源时才启动，且仅写临时副本。扩展加载异常也明确报错，不将丢失工具当作成功。Agent 有读取、bash 等实际工具能力，并非严格只读或权限沙箱；不要让不可信新闻资料驱动文件修改。DeepSeek 翻译、固定格式总结及其 Pi 翻译兜底保持原有链路，不在本轮迁移。

访问地址取决于 host/port；显式设置 `NEWS_READER_HOST` 的优先级高于 Tailscale 自动检测。本机无 Tailscale 时常用形式为 `http://127.0.0.1:<port>`。

## Tailscale

本机访问可配合 Tailscale 使用。项目内保留辅助脚本：

```bash
cd /Users/x/news-reader/news-reader
scripts/start-tailscale.sh
```

脚本会先读取终端环境变量 `DEEPSEEK_API_KEY`；若不存在，再从 macOS Keychain 的 `DEEPSEEK_API_KEY` service 读取；两者都没有时会报错退出。密钥满足后，脚本会读取/校验 Tailscale IPv4，使用该 IP 绑定 `NEWS_READER_HOST`，并直接执行 `python3 app.py` 启动 news-reader；运行脚本后无需再单独启动服务。Finder 一键启动脚本也会执行同样的 Tailscale IPv4 自动检测，但仍通过受控 supervisor 启动；显式 `NEWS_READER_HOST` 会覆盖自动检测。

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
- 新闻研究 Agent 的会话、消息、任务、原文快照和 Pi 临时 session 保存在独立临时位置；默认 TTL 为 72 小时，可在设置中改为 24 小时。“新会话”会物理删除本篇旧临时数据，设置页可清空全部；运行中的任务不因 TTL 清理，服务重启会将未结束任务标记为中断。这些数据不写入主库、sidecar 或常规备份。
- Agent 研究会话经 OAR 加载 Pi 配置与资源；权限和旧历史接续边界见上文；不受信任项目及需要 Pi 原生 MCP/codemode/tool_search/llama.cpp 的配置通过 Pi CLI 兼容模式继续，不擅自加载项目资源；新闻原文、用户引用和历史消息仅作为研究资料，不作为执行指令。外部来源应尽量给出 HTTP(S) 链接，无法联网或无法核实时如实说明。
- `.gitignore` 若存在用户本地脏改，除非任务明确要求，否则不得顺手纳入提交。
- release notes 统一更新 [CHANGELOG.md](CHANGELOG.md)，不要再把完整版本历史追加到 README。

## 内置安全更新

设置 → 更新中的“检查更新”只读取固定的 HTTPS 仓库 `https://github.com/xusz12/news-reader.git` 的稳定 `vN.N.N` 或 `vN.N.N.N` 形式 tag，预发布 tag 会被忽略。检查结果会生成短期一次性令牌；只有用户确认同一 tag、版本和 commit 后才会启动更新。

更新器拒绝 dirty 工作树、detached HEAD、历史分叉及非当前提交后代，只执行指定 tag 的 `git fetch` 和 `git merge --ff-only`，不执行 `reset --hard`、`git clean`、普通 `pull`，也不修改 `origin`。更新过程使用文件锁和状态文件，受控启动器会停止旧进程、启动新进程并检查 `/api/version` 的 commit；直接 `python3 app.py` 仍只启动当前版本，不执行自动更新。

Finder `.command` 与 `python3 updater.py --serve` 使用同一受控 supervisor。它持有单实例锁并跟踪自己启动的服务；更新器提交快进后请求 supervisor 重启新版本，健康失败时先安全回退再由 supervisor 恢复旧版本。健康 URL 匹配实际监听 host/port，通配监听地址使用本机 loopback 探测；每次服务启动另带独立实例标识，避免把端口上旧服务误认为新服务。更新进度与失败原因可在设置页查看，或读取只读 `/api/update/status`。新版本健康检查验证 `/api/version` 的 commit、首页、JavaScript 与样式资源；失败时仅在工作树保持干净、分支/HEAD 未被外部修改时执行 `git reset --keep` 回到旧 commit 并重新启动旧服务，无法安全回退时保留明确诊断状态，绝不覆盖用户修改。
