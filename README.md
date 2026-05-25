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
