# news-reader

本地新闻阅读器（Web 版），数据源来自 `DailyNews` 中的 `dailyFreshNews_*.md`。

## What's Changed

### 2026-06-01 — fix: 优化手机端详情阅读与右滑返回体验
- **文件**
  - *static/app.js（+5 −2）*
    - 右滑返回动画与阈值微调
  - *static/style.css（+54 −5）*
    - 详情区滚动与布局优化
- **影响**：手机端右滑返回更流畅

### 2026-06-01 — feat: 新增手机端详情页右滑返回交互
- **文件**
  - *static/app.js（+86 −0）*
    - touchstart/touchmove/touchend 手势识别，右滑超过阈值关闭详情
- **影响**：手机端右滑即可返回列表

### 2026-06-01 — feat: 重构手机端底部入口为集合与新闻源
- **文件**
  - *static/app.js（+63 −22）*
    - 底部双入口改为「新闻流」+「新闻源」tab
  - *static/index.html（+15 −4）*
    - 新增 mobileCollectionSheet 集合选择面板
  - *static/style.css（+1 −1）*
    - 底部 tab 样式调整
- **影响**：手机端底部导航更紧凑

### 2026-06-01 — fix: 调整手机端回到上次阅读仅定位列表行
- **文件**
  - *static/app.js（+3 −1）*
    - 回到上次阅读仅滚动列表至锚点行，不触发详情展开
- **影响**：手机端恢复阅读更精准

### 2026-06-01 — fix: 调整手机端筛选入口与安全区布局
- **文件**
  - *static/app.js（+4 −27）*
    - 筛选面板重构为底部 sheet
  - *static/index.html（+1 −5）*
    - 移除旧筛选入口
  - *static/style.css（+18 −22）*
    - 适配 safe-area-inset-bottom
- **影响**：手机端筛选面板不遮挡内容

### 2026-06-01 — feat: 完成手机端 Phase2 筛选入口与来源面板
- **文件**
  - *static/app.js（+107 −25）*
    - 新增 mobileFilterSheet 底部抽屉，整合集合切换 + 来源筛选
  - *static/index.html（+20 −0）*
    - 新增筛选抽屉 DOM 结构（遮罩、面板、header、来源列表）
  - *static/style.css（+108 −0）*
    - 底部抽屉动画、遮罩、面板布局样式
- **影响**：手机端可完整使用集合切换与来源筛选

### 2026-06-01 — feat: 完成手机端 Phase1 单栏与全屏详情导航
- **文件**
  - *static/app.js（+33 −6）*
    - 窄屏（≤980px）单栏布局，详情页全屏覆盖，新增返回按钮
  - *static/index.html（+6 −0）*
    - 新增移动端底部导航与详情返回按钮节点
  - *static/style.css（+82 −0）*
    - 单栏全宽、全屏详情、底部导航基础样式
- **影响**：手机端基础可用：列表浏览 + 全屏详情查看

### 2026-05-31 — chore: 移除列表底部到达提示
- **文件**
  - *static/app.js（+0 −10）*
    - 移除 `endBuffer` 元素引用及 `updateEndBufferVisibility()` 函数
  - *static/index.html（+0 −3）*
    - 移除 `endBuffer` DOM 节点
  - *static/style.css（+0 −11）*
    - 移除 `.end-buffer` 样式
- **影响**：列表底部不再显示"已到列表末尾"

### 2026-05-31 — fix: 右栏无摘要时隐藏摘要区占位提示
- **文件**
  - *static/app.js（+9 −1）*
    - 摘要为空时隐藏摘要区，不再显示"暂无摘要"占位文字
- **影响**：无摘要条目右栏更简洁

### 2026-05-31 — feat: 新增阅读偏好与主题显示优化
- **文件**
  - *static/app.js（+45 −0）*
    - 新增主题模式切换（跟随系统/浅色/深色），`localStorage` 持久化
    - 新增右栏字体大小切换（小/中/大），`localStorage` 持久化
  - *static/index.html（+14 −0）*
    - topbar 新增外观/右栏字体下拉选择器
  - *static/style.css（+189 −46）*
    - 全部硬编码颜色重构为 CSS 自定义属性（`--bg`/`--text`/`--border` 等）
    - 新增 `[data-theme="dark"]` 暗色主题变量及 `@media (prefers-color-scheme: dark)` 系统跟随
    - 新增 `[data-detail-font]` 字体缩放比例
    - 移动端 topbar 自适应网格布局
- **影响**：支持暗色模式与右栏字体调节

### 2026-05-30 — fix: 优化回到阅读按钮位置图标与刷新行为
- **文件**
  - *static/app.js（+11 −3）*
    - 回到阅读按钮调整位置与图标，刷新行为优化
  - *static/style.css（+4 −0）*
    - 按钮样式适配新位置
- **影响**：断点续连按钮更易发现与操作

### 2026-05-30 — feat: 新增阅读锚点断点续连能力
- **文件**
  - *app.py（+160 −22）*
    - 新增 `GET/PUT /api/reading-checkpoint` 端点，按 scope 读写阅读位置
    - 新闻排序重构为 `NEWS_ORDER_BY_SQL` 宏
  - *schema.sql（+8 −0）*
    - 新增 `reading_checkpoints` 表
  - *static/app.js（+94 −0）*
    - 自动保存当前可视第一条新闻为阅读锚点
    - 刷新 / 重新打开后检测锚点并显示「回到阅读位置」按钮
  - *static/index.html（+1 −0）*
    - 新增回到阅读位置按钮节点
  - *static/style.css（+9 −0）*
    - 回到阅读位置按钮样式
  - *tests/test_api.py（+83 −0）*
    - 新增 checkpoint 读写、scope 校验、PUT 字段验证测试
- **影响**：刷新列表后可从上次阅读位置继续，不丢失阅读进度

### 2026-05-30 — feat: 调整日期分段内新闻为旧到新排序
- **文件**
  - *app.py（+3 −1）*
    - 排序改为日期降序、日期内 `published_at` 升序（旧先新后）
  - *tests/test_api.py（+35 −0）*
    - 新增同日期内旧到新排序验证测试
- **影响**：每天新闻按时间正序排列，符合阅读习惯

### 2026-05-30 — fix: 优化日期分段左对齐与吸附展示
- **文件**
  - *static/style.css（+8 −6）*
    - 日期分段标题左对齐并优化 sticky 吸附效果
- **影响**：日期标题更整齐美观

### 2026-05-30 — feat: 新增中栏按日期 section 分段展示
- **文件**
  - *app.py（+23 −0）*
    - 新增 `derive_date_meta()` 生成日期标签（今天/昨天/YYYY年M月D日），API 每项返回 `date_key`/`date_label`
  - *static/app.js（+26 −4）*
    - 前端按 `date_key` 分组渲染并插入 sticky section 标题
  - *static/style.css（+19 −0）*
    - 日期 section 标题样式与吸附定位
  - *tests/test_api.py（+3 −0）*
    - 验证 API 返回 date_key/date_label 字段
- **影响**：新闻列表按自然日分段，定位更清晰

### 2026-05-30 — feat: 完成 news-reader v1.7.1 动态订阅源筛选
- **文件**
  - *app.py（+153 −0）*
    - 新增 `source_filter` 查询参数、`SOURCE_LABELS` 映射、`derive_source_key()` 域名/来源类型识别
    - 新增 `GET /api/sources` 端点返回可用来源及计数
    - where clause 构建提取为 `_build_news_where_clause()`
  - *static/app.js（+73 −2）*
    - 左栏新增来源筛选按钮列表，支持组合筛选（集合 + 来源 + 已读状态）
  - *static/index.html（+3 −0）*
    - 新增来源筛选按钮区域
  - *static/style.css（+15 −0）*
    - 来源筛选按钮样式
  - *tests/test_api.py（+59 −0）*
    - 新增 source_filter + sources 端点测试
- **影响**：可按来源（Reuters/Bloomberg/TechCrunch/Ars/X）独立筛选新闻

### 2026-05-29 — feat: 完成 v1.6 收口（重译与非文章内容交互优化）
- **文件**
  - *README.md（+）*
    - 新增 v1.6 能力说明并同步版本状态
  - *llm_client.py（+8 −2）*
    - `body_zh` 校验由固定长度阈值改为“非空 + 含中文字符”
  - *tests/test_llm_client.py（+62 −0）*
    - 新增短中文正文通过、纯英文正文拒绝测试
  - *static/app.js（+）*
    - 右栏移除稍后按钮，新增“重新翻译”交互与轮询状态优化
    - Bloomberg video 增加 `VIDEO` 标识与右栏 skip 文案
    - X/Twitter 中栏隐藏稍后按钮，右栏 skip 文案改为推文专用提示
  - *static/style.css（+）*
    - 新增 `VIDEO` badge 样式
- **影响**：短讯翻译不再误报 `INVALID_BODY_ZH`；video/推文在列表中可见但不误导正文抓取与稍后流程。

### 2026-05-29 — feat: 按集合切换批量按钮语义并支持清空稍后阅读
- **文件**
  - *app.py（+57 −0）*
    - 新增 `POST /api/news/clear-read-later` 端点，按集合批量取消稍后标记，同步取消 pending 的 detail/ai jobs
  - *static/app.js（+61 −13）*
    - 批量按钮语义随集合切换：feed「全部标已读」、read_later「全部看完」、important 隐藏
    - 稍后再看集合中详情/AI 就绪后自动取消稍后标记
    - 非 feed 集合自动切换 all 过滤，隐藏仅未读按钮
- **影响**：稍后再看集合中阅读完自动清标，一键清空所有稍后阅读

### 2026-05-28 — fix: 调整右栏操作按钮至摘要上方
- **文件**
  - *static/index.html（+6 −6）*
    - 操作按钮（打开原文/重试/重要/稍后再看）移至摘要上方
  - *static/style.css（+2 −1）*
    - 按钮区与滚动区间距调整
- **影响**：操作按钮更靠近标题，无需滚动即可操作

### 2026-05-28 — chore: 增加Keychain读取并优化Tailscale启动脚本
- **文件**
  - *README.md（+11 −0）*
    - 补充首次配置 Keychain 命令
  - *scripts/start-tailscale.sh（+16 −0）*
    - 优先复用终端 `DEEPSEEK_API_KEY`，不存在时从 macOS Keychain 读取
- **影响**：Keychain 持久化 API Key，不再依赖终端环境变量

### 2026-05-28 — fix: 稳定DeepSeek模型默认值并新增Tailscale启动脚本
- **文件**
  - *app.py（+8 −1）*
    - 启动监听地址/端口改为 `NEWS_READER_HOST` / `NEWS_READER_PORT` 环境变量
  - *llm_client.py（+8 −2）*
    - 模型名改为 `_configured_model()`，优先读 `NEWS_READER_LLM_MODEL`，默认 `deepseek-chat`
  - *README.md（+19 −0）*
    - 新增 Tailscale 启动、Keychain 配置、可选参数说明
  - *scripts/start-tailscale.sh（+23 −0）（新文件）*
    - 自动获取本机 Tailscale IPv4 并绑定启动，未连接时报错退出
  - *tests/test_llm_client.py（+41 −0）*
    - 新增模型配置读取与默认值回归测试
- **影响**：支持 Tailscale 局域网访问，LLM 模型可通过环境变量切换

### 2026-05-28 — fix: 修正内部滚动下自动已读顶部参照
- **文件**
  - *static/app.js（+2 −1）*
    - 自动已读判定从 `window.scrollY` 修正为 `newsList.scrollTop` + 列表 `getBoundingClientRect().top`
- **影响**：内部滚动模式下自动已读触发更准确

### 2026-05-28 — fix: 固定中栏顶部并修正底部提示显示
- **文件**
  - *static/app.js（+27 −7）*
    - 控件区不再 sticky，随内容自然滚动
    - hint/sentinel 移入新闻列表内部，新增 `appendNewsRow()` 确保插入位正确
    - `resetList()` 改为精确移除 `.news-item` 而非清空整个列表
  - *static/index.html（+5 −4）*
    - hint/sentinel 从独立位置移入 `<ul>` 列表内
  - *static/style.css（+17 −9）*
    - feed-column 改为 flex column + overflow hidden，控件区 flex 0 0 auto
    - end-buffer 改为 flex 0 0 auto + min-height: 0
- **影响**：中栏内部独立滚动，控件不再遮挡列表

### 2026-05-28 — fix: 统一右栏摘要要点正文滚动区域
- **文件**
  - *static/index.html（+14 −12）*
    - 新增 `detail-scroll-area` 容器包裹摘要/AI/状态/正文/原文折叠区
  - *static/style.css（+6 −8）*
    - 移除 detail-summary、detail-content、detail-ai-box 各自独立的 max-height/overflow
    - 统一由 `detail-scroll-area` flex:1 + overflow-y:auto 接管
- **影响**：右栏滚动行为统一，避免多段各自滚动导致跳位

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
脚本会优先使用当前终端已有的 `DEEPSEEK_API_KEY`，若不存在则自动尝试从 macOS Keychain 读取：

```bash
security find-generic-password -a news-reader -s DEEPSEEK_API_KEY -w
```

首次配置 Keychain（一次即可）：

```bash
security add-generic-password -a news-reader -s DEEPSEEK_API_KEY -w '你的key' -U
```

## 测试

```bash
cd /Users/x/Library/Mobile Documents/com~apple~CloudDocs/slock项目/news-reader
python3 -m pytest -q
```

## 数据与 Git 边界

- 代码入库：源码、schema、测试、文档
- 运行数据不入库：`*.sqlite3`, `*.sqlite3-wal`, `*.sqlite3-shm`
- 缓存不入库：`__pycache__/`, `.pytest_cache/`, `.DS_Store`

---

后续每次更新请在本文件末尾追加一条 `What's Changed` 记录（日期 + 变化点）。
