# news-reader

本地新闻阅读器（Web 版），数据源来自 `DailyNews` 中的 `dailyFreshNews_*.md`。

## 项目能力

### v1.0（已完成）
- 本地 Web 列表页（RSS-like）
- 仅扫描 `DailyNews/**/dailyFreshNews_*.md`
- 新闻按发布时间倒序展示
- 点击标题新标签页打开原文链接
- 关键词搜索（标题/摘要/来源）
- 分页浏览
- 手动刷新索引（增量扫描）

### v1.1（已完成）
- 已读/未读状态（`item_state.read_at`）
- 未读红点提示（已读不再灰度）
- `全部显示` / `仅未读` 过滤
- 单条 `标为已读` / `标为未读`
- `当前结果全部标为已读`（按当前筛选条件，跨分页生效）
- 点击原文自动标已读
- 自动已读（向下滚动后条目滑出屏幕顶部触发）
- 列表底部阅读缓冲区（约 `100vh`）

### v1.2（进行中）
- 增加双状态标记：`重要`（`important_at`）与`稍后再看`（`read_later_at`），允许共存、独立撤销。
- 三栏工作台：左栏集合入口（新闻流/重要/稍后），中栏连续信息流，右栏摘要与标记操作。
- 中栏保留通用控制：`全部显示/仅未读`、搜索、跨页批量标已读、刷新索引。
- 组合筛选支持：`collection=feed|important|read_later` 与 `read_filter=all|unread` 叠加。
- 窄屏降级：详情区改为底部抽屉，保证移动端可用。

## 技术结构

- 后端：Flask + SQLite
- 前端：原生 HTML/CSS/JS
- 解析器：项目内独立 `parser.py`（不依赖 `news-briefing` 脚本）
- 索引更新：`source_files(path+mtime+size)` 增量机制 + upsert + stale delete

## 运行方式

```bash
cd /Users/x/Library/Mobile Documents/com~apple~CloudDocs/slock项目/news-reader
python3 -m pip install -r requirements.txt
python3 app.py
```

浏览器访问：<http://127.0.0.1:8080>

可选启动参数（默认仍仅本机访问）：

```bash
# 默认：127.0.0.1:8080
NEWS_READER_HOST=127.0.0.1 NEWS_READER_PORT=8080 python3 app.py

# Tailscale/局域网访问时显式开放监听
NEWS_READER_HOST=0.0.0.0 NEWS_READER_PORT=8080 python3 app.py
```

手机 Tailscale 访问（推荐）：

```bash
./scripts/start-tailscale.sh
```

脚本会自动读取当前 Mac 的 Tailscale IPv4 并绑定该地址启动服务；若未连接 Tailscale，会直接报错退出。

## 测试

```bash
cd /Users/x/Library/Mobile Documents/com~apple~CloudDocs/slock项目/news-reader
python3 -m pytest -q
```

## 数据与 Git 边界

- 代码入库：源码、schema、测试、文档
- 运行数据不入库：`*.sqlite3`, `*.sqlite3-wal`, `*.sqlite3-shm`
- 缓存不入库：`__pycache__/`, `.pytest_cache/`, `.DS_Store`

## What's Changed

### 2026-05-28 — feat: 完成v1.4正文翻译总结与右栏中文展示
- **文件**
  - *app.py（+205 −14）*
    - `DETAIL_COMMAND_ROUTES` 重构为 dict，支持每域名独立 timeout；新增 Bloomberg 视频跳过
    - 详情抓取成功后自动入队 AI 翻译任务（`enqueue_ai_job`）
    - 新增 `process_pending_ai_once`，worker 线程顺序处理 AI 翻译队列
    - `detail_worker_loop` 扩展为抓取+AI 双队列串行处理
    - `GET /api/news` 联表 `ai_jobs` + `article_ai`，返回 `ai_status`/`ai_error`/`ai_ready`
    - `GET /api/news/:id/detail` 新增 AI 任务状态与翻译结果字段
    - `POST /api/news/:id/detail/retry` 已有正文时优先重试 AI，否则从抓取重新开始
    - 取消稍后再看同步取消 pending 状态的 AI 任务
  - *llm_client.py（+114 −0）（新文件）*
    - 基于 OpenAI SDK 调用 DeepSeek API，使用 structured tool calling
    - strict function-calling 默认模型为 `deepseek-chat`（映射 v4-flash 非思考模式），可通过 `NEWS_READER_LLM_MODEL` 切换
    - `generate_article_ai()` 输出 3-5 条中文要点、一句话结论、完整中文翻译
    - 严格校验返回值（字段类型、列表长度、正文长度 >= 200 字符）
  - *requirements.txt（+1 −0）*
    - 新增 `openai==1.82.0`
  - *schema.sql（+24 −0）*
    - 新增 `ai_jobs` 表（url 主键、状态、重试计数、时间戳）及状态索引
    - 新增 `article_ai` 表（url 主键、model、要点 JSON、结论、中文正文、原始 JSON）
  - *static/app.js（+87 −8）*
    - 详情区新增中文要点列表、结论、完整中文翻译展示
    - AI 状态行显示（排队中/正在翻译/已完成/失败/已跳过）
    - 详情数据缓存扩展至 AI 字段，AI 轮询联动现有 detail 轮询
    - 新增 `<details>` 折叠组件切换英文原文/中文翻译
    - 恢复 read_later / 重试 / 选中切换时联动 AI 状态刷新
  - *static/index.html（+10 −1）*
    - 详情面板新增 AI 区块（要点列表、结论、中文正文）及英文原文折叠区
  - *static/style.css（+57 −3）*
    - 新增 AI 区块样式：要点列表、结论高亮、原文折叠区、翻译正文区
  - *tests/test_api.py（+61 −0）*
    - 新增 AI 联表字段回归测试、详情重试分支（有正文/无正文）测试
  - *tests/test_llm_client.py（+78 −0）（新文件）*
    - 新增 `generate_article_ai` 参数校验、返回值结构、错误码测试
- **影响**：原文抓取成功后自动翻译为中文，右栏展示要点、结论与完整中文翻译，支持切换查看英文原文

### 2026-05-27 — feat: 新增稍后再看详情抓取系统
- **文件**
  - *app.py（+344 −7）*
    - 新增 `detail_jobs` 队列 + `article_details` 存储 + 后台 worker 线程，按 URL 幂等排重
    - 集成 opencli 子进程抓取 4 个域名正文（reuters、bloomberg、techcrunch、arstechnica），X/Twitter 跳过
    - `PATCH /api/news/:id/state` 标记稍后再看时自动入队详情任务，取消时仅取消 pending 不杀 running
    - 新增 `GET /api/news/:id/detail` 查询详情状态与正文
    - 新增 `POST /api/news/:id/detail/retry` 手动重试失败任务
    - 应用启动时自动启动 detail worker
  - *schema.sql（+28 −0）*
    - 新增 `detail_jobs` 表（url 主键、状态、重试计数、时间戳）及状态索引
    - 新增 `article_details` 表（url 主键、正文、元信息、原始 JSON）
  - *static/app.js（+149 −4）*
    - 右栏详情区展示抓取状态（排队中/正在抓取/已完成/失败/已跳过）、正文内容、重试按钮
    - 标记稍后再看时自动拉取详情，2 秒轮询直到完成/失败/跳过
    - 标记稍后再看按钮状态色联动：黄色=等待中、绿色=详情就绪、红色=失败
    - 取消稍后再看/切换条目/重置列表时停止轮询、清空缓存
    - 新增 `detailCacheByUrl` 缓存避免重复请求
  - *static/index.html（+3 −0）*
    - 详情区新增状态行、正文区、重试按钮三个 DOM 节点
  - *static/style.css（+47 −2）*
    - 新增详情状态色（muted/pending/ready/failed）、正文滚动区、重试按钮样式
    - 详情面板改为 flex column 布局
  - *tests/test_api.py（+50 −0）*
    - 新增测试：标记稍后再看触发入队、取消后状态变更、retry 端点可用
- **影响**：标记稍后再看时自动异步抓取原文正文，右栏详情区可查看抓取进度与完整内容

### 2026-05-26 — feat: 完成 news-reader v1.2 三栏工作台与重要稍后标记
- **文件**
  - *app.py（+46 −9）*
    - `GET /api/news` 新增 `collection` 与 `read_filter` 组合查询，返回三种状态时间字段
    - `PATCH /api/news/:id/state` 扩展为独立设置/撤销 `read`、`important`、`read_later`
    - `POST /api/news/mark-all-read` 新增 `collection` 约束
  - *README.md（+17 −0）*
    - 补充 v1.2 能力说明与 What's Changed 记录
  - *scanner.py（+8 −0）*
    - 扫描逻辑适配新字段
  - *schema.sql（+2 −0）*
    - 新增 `important_at`、`read_later_at` 字段
  - *static/app.js（+322 −88）*
    - 三栏布局交互：集合切换、组合筛选、右栏摘要与双入口标记操作
    - 统一内置 SVG 图标替代文本按钮
  - *static/index.html（+42 −22）*
    - 三栏工作台布局：左栏集合入口、中栏信息流、右栏摘要
  - *static/style.css（+279 −47）*
    - 三栏布局样式、窄屏抽屉降级、SVG 图标状态色（重要/稍后）
  - *tests/test_api.py（+67 −0）*
    - 新增 `collection` + `read_filter` 组合查询与状态切换测试
- **影响**：新增重要/稍后再看双标记，三栏工作台替代原单栏布局

### 2026-05-25 — feat: 完成 news-reader v1.1.2 自动刷新下滑加载与本地图标
- **文件**
  - *README.md（+6 −0）*
    - 补充 v1.1.2 能力说明
  - *static/app.js（+215 −97）*
    - 页面初始化自动增量索引刷新，失败回退本地索引
    - 列表改为连续下滑追加加载，隐藏分页按钮
    - 信息行重排为 `[图标] source · published_at`
  - *static/index.html（+3 −1）*
    - 列表容器适配下滑加载
  - *static/source-icons/arstechnica.ico（新增）*
    - arstechnica 本地 favicon
  - *static/source-icons/bloomberg.png（新增）*
    - bloomberg 本地 favicon
  - *static/source-icons/reuters.ico（新增）*
    - reuters 本地 favicon
  - *static/source-icons/techcrunch.png（新增）*
    - techcrunch 本地 favicon
  - *static/source-icons/x.svg（+4 −0）*
    - 推文统一本地 X 图标
  - *static/style.css（+35 −0）*
    - 信息行图标与来源排版样式
- **影响**：自动刷新索引 + 下滑加载替代手动刷新与分页按钮；媒体来源使用本地图标

### 2026-05-25
- 新增 README，补充能力说明与变更记录入口。

### 2026-05-25（v1.1）
- 新增已读/未读能力：`read_filter`、单条状态切换、跨页批量已读。
- 新增自动已读：向下滚动且条目滑出屏幕顶部后标已读。
- UI 调整：未读红点替代已读灰度，并加入底部阅读缓冲区。
- 保持 `schema/scanner/parser` 边界不变，`reindex` 不触碰 `item_state`。

### 2026-05-25（v1.0）
- 新建 news-reader 基线：dailyFreshNews 列表、倒序排序、原文跳转、增量索引、基础 API 与测试。

---

后续每次更新请在本文件末尾追加一条 `What's Changed` 记录（日期 + 变化点）。
