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

### 2026-05-25（v1.2）
- 后端新增状态字段与迁移兼容：`important_at`、`read_later_at`（保留既有 `read_at`）。
- `GET /api/news` 支持 `collection` 与 `read_filter` 组合查询并返回三种状态时间字段。
- `PATCH /api/news/:id/state` 扩展为独立设置/撤销 `read`、`important`、`read_later`。
- `POST /api/news/mark-all-read` 新增 `collection` 约束，确保跨页批量仅作用于当前集合。
- 前端升级三栏布局与右栏摘要工作区，支持在列表与详情中双入口操作 `重要/稍后再看`。
- 交互控件改为统一内置 SVG 图标：中栏顶部保留 3 个符号按钮（显示状态切换、全部标读、刷新）；移除搜索框与单行读/未读按钮。
- 状态图标规则：重要为灰色空心/红色填充感叹号，稍后为灰色空心/黄色填充书签；本版暂不实现绿色“详情就绪”态。
- 保持不做：正文抓取、翻译总结、归档与自动推荐。

### 2026-05-25（v1.1.2）
- 页面初始化自动执行增量索引刷新（失败时回退展示本地索引并提示可重试）。
- 列表改为连续下滑追加加载（隐藏分页按钮，保留原 `page/per` API）。
- 信息行重排为 `[图标] source · published_at`，媒体来源优先使用本地缓存 favicon，推文统一使用本地 X 图标，未知来源使用统一兜底图标。
- 保持 schema/parser/scanner 不变，已读交互能力不回归。

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
