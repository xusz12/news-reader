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
- 已读行灰度显示
- `全部显示` / `仅未读` 过滤
- 单条 `标为已读` / `标为未读`
- `当前结果全部标为已读`（按当前筛选条件，跨分页生效）
- 点击原文自动标已读
- 自动曝光标已读（自适应可见高度 + 持续 2 秒）

## 技术结构

- 后端：Flask + SQLite
- 前端：原生 HTML/CSS/JS
- 解析器：项目内独立 `parser.py`（不依赖 `news-briefing` 脚本）
- 索引更新：`source_files(path+mtime+size)` 增量机制 + upsert + stale delete

## 运行方式

```bash
cd /Users/x/news-reader
python3 -m pip install -r requirements.txt
python3 app.py
```

浏览器访问：<http://127.0.0.1:8080>

## 测试

```bash
cd /Users/x/news-reader
python3 -m pytest -q
```

## 数据与 Git 边界

- 代码入库：源码、schema、测试、文档
- 运行数据不入库：`*.sqlite3`, `*.sqlite3-wal`, `*.sqlite3-shm`
- 缓存不入库：`__pycache__/`, `.pytest_cache/`, `.DS_Store`

## What's Changed

### 2026-05-25
- 新增 README，补充能力说明与变更记录入口。

### 2026-05-25（v1.1）
- 新增已读/未读能力：`read_filter`、单条状态切换、跨页批量已读。
- 新增自动曝光标已读：`visibleHeight >= min(rowHeight*0.75, viewportHeight*0.60)` 且持续 2 秒。
- 保持 `schema/scanner/parser` 边界不变，`reindex` 不触碰 `item_state`。

### 2026-05-25（v1.0）
- 新建 news-reader 基线：dailyFreshNews 列表、倒序排序、原文跳转、增量索引、基础 API 与测试。

---

后续每次更新请在本文件末尾追加一条 `What's Changed` 记录（日期 + 变化点）。
