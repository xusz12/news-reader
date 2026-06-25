# news-reader

本地新闻阅读器（Web 版），数据源来自 `DailyNews` 中的 `dailyFreshNews_*.md`。

## What's Changed

### 2026-06-25 — v1.9.8.9 feat: 板块工作台整合总览、单板块混合流与近期总结
- **文件**
  - *schema.sql（+）*、*app.py（+）*、*llm_client.py（+）*、*tests/test_api.py（+）*
    - 新增 `market_tag_summaries` 缓存表，以及板块工作台接口 `GET /api/market-workbench`、板块总结接口 `GET/POST /api/market-tags/:tag/summary`
    - “全部板块”视图改为轻量总览卡片，只汇总近 30 天新闻分布、看多/看空、独立趋势想法数量和最近更新时间，不再加载全量新闻历史
    - 单板块专区改为混合流：同一时间线里同时返回板块新闻与独立趋势想法，并支持 `全部 / 仅想法 / 看多 / 看空` 四种筛选
    - 新增单板块“总结近期趋势”手动触发链路：默认最近 30 天、最多 50 条本地新闻，prompt 显式拆分“新闻事实 / 用户想法”，失败仅影响总结区，不阻塞浏览
    - 摘要缓存按 `tag + range_days + source_hash` 判断 `未生成 / 已过期 / 生成失败 / 已生成`，新闻、新闻想法或独立趋势想法更新后不会静默沿用旧总结
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - `板块` 入口升级为“板块工作台”，新增板块选择、内容筛选、近期趋势总结区与全部板块总览卡片
    - 单板块流中点击新闻仍打开原右栏详情；点击独立趋势想法仍复用现有趋势想法详情 / 编辑 / 删除链路
    - 左侧 `趋势` 入口降为隐藏兼容入口，旧趋势 API 继续保留给既有详情链路复用
- **影响**：板块与趋势的日常使用入口被合并成一个更直接的工作台，用户可以先看全局板块分布，再进入单板块专区浏览“新闻 + 想法”混合流，并在需要时手动生成近期趋势总结。

### 2026-06-23 — v1.9.8.8 fix: 时间流布局与版本号小修
- **文件**
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 修正顶部 title 旁版本号、页面 `<title>` 与样式版本参数，统一更新为 `v1.9.8.8`
    - 时间流左侧时间轴改为更贴近内容边缘的细竖线 + 圆点；日期移到对应卡片上方，并与圆点水平对齐
    - 时间流卡片头部改为单行操作区：副标题、生成/重新生成、展开原始新闻符号同排展示，字体与视觉层级统一
    - 展开原始新闻按钮改成仅显示下拉符号，原始新闻列表仍在卡片底部展开，点击打开新闻详情逻辑不变
- **影响**：时间流阅读顺序更接近“日期标题 + 当日卡片”的时间线结构，操作区更紧凑，顶部版本号也与当前版本保持一致。

### 2026-06-23 — v1.9.8.7 feat: 默认匹配参数与必要关键词
- **文件**
  - *settings.py（+）*、*app.py（+）*、*tests/test_api.py（+）*
    - `app_settings.json` 扩展 `tracked.default_rule_params`，持久化保存新建跟踪主题使用的默认数字参数
    - 新增 `PUT /api/settings/tracked-default-rule-params`，只更新 tracked 默认参数；`GET /api/settings` 也会返回当前默认值
    - `tracked_topics.rules_json` 新增 `required_terms`，匹配顺序改为：先排除词，再必要关键词，再进入原有 strong/core/context 评分
    - 历史回扫在 `required_terms` 变化后会重算旧自动命中；手动加入保留、手动隐藏不复活；`reason` 补充必要词命中证据
    - 补覆盖：默认参数 roundtrip、新建主题继承默认数值、necessary gate / exclude 优先级、required_terms 变更后的 backfill 仍保留 manual/hidden override
  - *static/index.html（+）*、*static/app.js（+）*
    - 跟踪页新增独立 `默认参数` 入口，右栏可维护标题 / 想法 / 摘要 / 正文倍率、规则得分与最低收录分数，并支持 `恢复系统默认`
    - 跟踪主题编辑页新增 `保存当前参数为默认` 快捷动作，但只写全局默认参数，不改其它主题
    - 新建 / 编辑跟踪主题表单新增 `必要关键词` 输入区；新建表单数字优先读取全局默认参数
    - `一键填写` 继续只生成关键词草稿，不再覆盖阈值等数字默认值
- **影响**：用户现在可以长期维护一套“新建跟踪主题默认数字口径”，同时用必要关键词给宽主题增加硬门槛，减少误收且不影响已有主题参数。

### 2026-06-23 — v1.9.8.6 feat: LLM 辅助生成跟踪主题规则
- **文件**
  - *llm_client.py（+）*、*app.py（+）*、*tests/test_api.py（+）*、*tests/test_llm_client.py（+）*
    - 新增 DeepSeek 结构化 `tracked rule draft` 生成链路，返回 `title / strong_phrases / core_terms / context_terms / exclude_terms / threshold`
    - 新增 `POST /api/tracked-topics/rule-draft` 非持久化接口：只生成草稿，不创建主题、不回扫、不写 `tracked_topic_items`
    - 后端对 LLM 返回执行本地清洗：trim、去重、去空、过滤超长词、限制条目数量、将 threshold 约束到合理范围
    - 补覆盖：空标题错误、草稿生成不持久化、脏词/重复词清洗、草稿可继续走现有 `POST /api/tracked-topics` 保存、LLM 非法结构报错
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 新建跟踪主题表单的主题名称输入框旁新增 `一键填写` 按钮
    - 主题名称为空时不给调用；已有规则内容时先确认是否覆盖；生成失败不会清空已有输入
    - 草稿生成成功后按当前表单接受的逗号分隔格式直接预填规则字段，用户仍需手动检查后再保存
- **影响**：用户现在可以先输入主题名称，再用 LLM 快速生成一版跟踪规则草稿，减少手工搭模板成本，同时保留人工审核和修改权。

### 2026-06-23 — v1.9.8.5 fix: 跟踪时间流字数约束与深色可读性
- **文件**
  - *app.py（+）*、*llm_client.py（+）*、*tests/test_api.py（+）*、*tests/test_llm_client.py（+）*
    - 时间流单日总结新增动态字数上限：按新闻数计算 `min(600, max(120, N*50))`，并把上限显式写入 DeepSeek prompt
    - 后端新增超长摘要安全兜底：优先在自然断点截断，找不到断点再硬截断并补省略号，不再发起二次 LLM 调用
    - 将时间流摘要版本与字数预算纳入缓存 hash，旧版 v1.9.8.4 摘要会转为 `已过期`，不会静默沿用
    - 为时间流展开原始新闻补 `has_detail` 字段，并补覆盖：动态上限、超长截断、旧缓存过期、prompt 上限约束
  - *static/app.js（+）*、*static/style.css（+）*
    - 修复时间流在深色外观下的日期、时间轴、摘要正文、展开原始新闻列表可读性，统一改走现有主题变量
    - 跟踪原始新闻列表与时间流展开原始新闻列表中，已缓存正文的新闻新增 `正文` 标记
- **影响**：时间流摘要长度现在更稳定，旧缓存会提示重生成；深色模式下的时间流更易读，且用户能更快识别哪些原始新闻已具备本地正文详情。

### 2026-06-23 — v1.9.8.4 feat: 跟踪时间流总结视图
- **文件**
  - *schema.sql（+）*、*app.py（+）*、*llm_client.py（+）*、*tests/test_api.py（+）*
    - 新增 `tracked_topic_daily_summaries` 缓存表，以及 `GET /api/tracked-topics/:id/daily-summaries`、`POST /api/tracked-topics/:id/daily-summaries/:date/generate`
    - 按跟踪主题和日期聚合已命中的本地新闻，生成 `未生成 / 已生成 / 已过期 / 生成失败` 状态；新闻集合变化时只标记过期，不静默覆盖旧摘要
    - 时间流单日总结默认调用 DeepSeek，输入仅使用本地已入库的标题、摘要、AI 摘要、正文、用户想法等事实材料，不联网、不抓新网页
    - 补覆盖：新表与索引建库、单日生成成功/失败、按发布时间顺序组织材料、手动加入后摘要转为过期
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 跟踪主题右栏新增 `原始新闻 / 时间流` 视图切换，默认仍停留在原始新闻时间线
    - 时间流视图改为左侧纵向时间轴，日期节点右侧直接展示当天融合摘要；摘要下方可弱化展开当天原始新闻列表
    - 单日摘要改为手动生成/重生成，打开页面不会自动批量触发 LLM
- **影响**：用户现在可以在不改变原始新闻时间线的前提下，按日期查看同一主题的“时间流”压缩总结，并且随时展开回看当天原始新闻做事实核查。

### 2026-06-22 — v1.9.8.3 improve: 跟踪回扫重算与权重可调
- **文件**
  - *app.py（+）*、*tests/test_api.py（+）*
    - 跟踪历史回扫从“增量追加”改为“按当前规则在所选范围内重新计算并覆盖旧自动命中”，旧自动误命中可被清理；手动加入保留、手动隐藏不复活
    - `rules_json` 扩展为可承载字段倍率与规则强度：标题 / 想法 / 摘要 / 正文倍率，以及强短语 / 核心词 / 场景词 / 排除强度 / 最低收录分数；倍率和强度支持浮点数
    - 自定义倍率与得分会实际参与 `score` 计算，并继续输出可解释 `reason`
    - 补覆盖：规则变更后回扫会清掉旧 auto 命中、manual/hidden override 保持、非 important 全量回扫重算、自定义 note 浮点权重影响命中与分数
  - *static/index.html（+）*、*static/app.js（+）*
    - 跟踪编辑页移除“主题摘要 / 关注角度 / 补充说明”输入框，仅保留规则本身
    - 跟踪编辑页新增可调数字输入：字段倍率与规则得分；每个输入补了明确标题，且支持浮点步进
    - 点击“回扫历史新闻”前增加确认警告，明确会按当前规则重新计算并覆盖旧自动匹配结果
- **影响**：修改跟踪规则后，用户现在可以真正重扫并刷新旧自动命中结果，不再需要依赖增量追加；同时可按主题特点手动调节各字段与规则强度。

### 2026-06-22 — v1.9.8.2 fix: 跟踪页回扫范围与规则说明
- **文件**
  - *app.py（+）*、*tests/test_api.py（+）*
    - 跟踪历史回扫新增 `全部新闻` 模式，可在全部已索引新闻范围内按当前规则重算自动命中，同时继续保持手动加入保留、手动隐藏不复活
    - 跟踪主题时间线改为按新闻发布时间 `新 -> 旧` 展示，最新进展默认置顶
    - 补覆盖：`全部新闻` 能扫到非 important 命中、旧回扫模式不回归、override 语义在新模式下继续成立、时间线排序改为倒序
  - *static/index.html（+）*、*static/app.js（+）*
    - 回扫下拉框新增 `全部新闻`，并补充“可能更慢、噪音更多”的简短提示
    - 右栏跟踪规则表单新增字段理解说明与打分说明，明确 `标题 > 用户想法 > 摘要/AI 摘要 > 正文`，正文单独命中不收录，排除词优先
- **影响**：用户现在可以在建立长期主题时直接补扫全部历史新闻，并且能在界面内更清楚地理解每个规则字段和打分逻辑；时间线也更适合查看最新进展。

### 2026-06-22 — v1.9.8.1 fix: 跟踪匹配规则降噪
- **文件**
  - *schema.sql（+）*、*scanner.py（+）*、*app.py（+）*、*tests/test_api.py（+）*
    - `tracked_topics` 新增 `rules_json`，旧库启动时自动补 migration；旧主题若只有 `keywords_json / exclude_keywords_json`，会在读取时自动映射成结构化规则
    - tracked 匹配从“任一关键词命中即收录”升级为“强短语 / 核心词 / 场景词 / 排除词 + 分数字段权重”，并保留手动加入、隐藏后不复活等 override 语义
    - 新增可解释命中证据：按标题 / 笔记 / 摘要 / 正文字段记录命中词并写入 `tracked_reason`，格式如 `标题命中：乌克兰/袭击；score=8`
    - 补覆盖：旧库 `rules_json` 建库幂等、单个宽泛词不误收、标题/笔记/摘要/正文权重、content-only 不入主时间线、排除词 veto、手动加入/隐藏不回归
  - *static/index.html（+）*、*static/app.js（+）*
    - 跟踪主题右栏表单从旧“包含/排除关键词”改为 `强匹配短语 / 核心对象词 / 相关场景词 / 排除词 / 最低收录分数`
    - 主题详情摘要同步展示结构化规则与阈值，时间线默认显示新的规则证据文案
- **影响**：跟踪主题对“俄罗斯 / AI”这类宽词的误命中会明显下降，正文长文单独出现关键词也不会直接进主时间线；但旧主题与回扫入口仍保持兼容。

### 2026-06-22 — v1.9.8.0 improve: 跟踪页 MVP
- **文件**
  - *schema.sql（+）*、*app.py（+）*、*tests/test_api.py（+）*
    - 新增 `tracked_topics / tracked_topic_items` 两张表与索引，独立保存跟踪主题定义、关键词规则、手动加入/移除 override 与缓存后的匹配关系
    - 新增 `GET/POST/PATCH/DELETE /api/tracked-topics`、`GET /api/tracked-topics/:id/items`、`POST /api/tracked-topics/:id/backfill`、`POST/PATCH /api/tracked-topics/:id/items`
    - `POST /api/reindex` 结束后会对 active topics 做增量匹配；历史回扫仅支持 `近180天重要新闻` 与 `全部重要新闻` 两档
    - 补覆盖：tracked 表/索引建库幂等、回扫范围、增量匹配、手动移除不复活、手动加入长期保留
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 左侧栏和移动端集合面板新增「跟踪」，位置在「想法」之后、「板块」之前
    - 新增独立跟踪页：主题列表、主题详情时间线、历史回扫按钮与范围选择、删除/编辑、空态提示
    - 主题时间线按新闻发布时间旧→新展示，点击新闻继续复用现有右侧新闻详情
    - 新闻右侧详情新增“加入跟踪主题”入口，支持把当前新闻手动加入任意 active 跟踪主题
- **影响**：News Reader 现在可以把长期事件/主题沉淀成持续更新的时间流；第一版只做确定性规则匹配与人工纠偏，不做 LLM 全史总结、关键转折判断或知识图谱。

### 2026-06-21 — v1.9.7.5 improve: 趋势想法右侧栏详情与编辑删除
- **文件**
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 为想法集合里的 `trend_note` 新增独立右侧栏详情视图，点击后不跳趋势页，而是在右侧展示全文、板块/日期/方向、创建/更新时间
    - 右侧栏新增编辑与删除动作：编辑直接复用现有 trend note 更新接口，删除带二次确认；保存/删除后同步更新或移除想法集合 row
    - 保持 v1.9.7.4 A 口径：趋势想法 row 仍完整展示全文；新闻想法点击继续打开新闻右栏，不受影响
- **影响**：用户现在可以在统一“想法”集合里直接查看、编辑、删除趋势想法，而不必切回趋势页；本版只扩展右侧详情展示层，不改变底层两张想法表及趋势页原有流程。

### 2026-06-21 — v1.9.7.4 improve: 想法集合统一展示新闻想法与趋势想法
- **文件**
  - *app.py（+）*、*tests/test_api.py（+）*
    - 新增 `GET /api/ideas`，把 `article_notes` 与 `market_trend_notes` 按想法 `updated_at` 统一查询为混合 feed，但底层仍保持两张表独立
    - 支持 `type=all|article|trend` 与 `sort_order=default|reverse`，并补覆盖：混合列表、类型筛选、趋势想法删除后同步、旧 `collection=notes` 不回归
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 左侧“想法”集合改走统一 ideas feed，顶部新增 `全部 / 新闻想法 / 趋势想法`
    - 卡片显式区分“新闻想法 / 趋势想法”；新闻想法点击继续打开新闻右栏，趋势想法则在 row 内完整展示全文且不再跳转
    - “想法”集合的排序按钮语义改为按想法更新时间正/反序；同时隐藏不再适用的来源筛选
- **影响**：用户现在可以在一个入口里回看新闻想法与趋势想法，但新闻笔记与趋势笔记的写入、编辑、删除语义保持原样不混淆。

### 2026-06-21 — v1.9.7.3 improve: Chat 归档到新闻想法
- **文件**
  - *app.py（+）*、*tests/test_api.py（+）*
    - 新增 `POST /api/news/:id/chat/archive`，把当前 chatPage 可见对话压缩为不超过 100 字的中文归档结论，并追加写入 `article_notes`
    - 归档仅复用现有新闻想法表，不保存完整 transcript、不新增 schema；无 assistant 回答、Codex 失败、摘要无效或追加后超 5000 字时都不会写入
    - 补覆盖：首次归档写入、已有想法时追加、无 assistant 拒绝、超长拒绝且旧想法不变、Codex 失败不落库
  - *static/index.html（+）*、*static/app.js（+）*
    - chatPage 在发送按钮旁新增 `归档` 按钮，仅在已有 assistant 回复且当前未发送时可用
    - 归档成功后同步更新右栏“我的想法”、新闻 row 的想法状态与 `note_preview`
- **影响**：用户现在可以把一轮新闻提问压缩为可复用结论并沉淀到该新闻自己的想法内，但不会把完整聊天过程原样存入笔记。

### 2026-06-21 — v1.9.7.1 fix: 提醒集合与表单交互收口
- **文件**
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - “添加提醒”表单改为：事件标题默认使用新闻标题且不再可编辑
    - 去掉冗余的 datetime 选择，仅保留日期选择；保存时提醒时间统一默认 `08:00`
    - 提醒集合顶部新增 `进行中 / 已完成 / 全部` 切换；已完成提醒不再因标记完成而消失
    - 提醒集合卡片与正文提醒区去掉重复新闻标题，改为展示日期、状态、备注等辅助信息；已完成提醒使用弱化样式保留
    - 中栏新闻 row 按钮顺序调整为：重要、稍后、收藏
    - 右栏“提问”按钮移到右侧交互区，并改为对话气泡图标按钮
- **影响**：提醒创建/回看路径更收敛，完成提醒可持续留存在集合与正文页中，且提醒信息层级不再重复；本版仅前端调整，不改后端 schema。

### 2026-06-20 — v1.9.7.0 feat: 新闻事件提醒集合
- **文件**
  - *schema.sql（+）*、*app.py（+）*
    - 新增独立 `news_reminders` 表与索引，提醒不再塞进 `item_state`
    - 新增 `GET /api/reminders`、`GET /api/reminders/summary`、`POST /api/news/:id/reminders`、`PATCH /api/reminders/:id`、`DELETE /api/reminders/:id`
    - `/api/news`、`/api/news/status`、`/api/news/:id/detail` 同步返回 active reminder 数量、到期数量与详情摘要
    - reminder 保留新闻标题/原文快照；新闻被 reindex 删掉后，提醒仍可在集合中继续展示
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 左栏与移动端集合入口新增“提醒”，支持到期数量提示
    - 右栏正文区新增“添加提醒”按钮、提醒编辑表单与提醒列表
    - 提醒集合改为独立提醒卡片流，按 `remind_at` 排序，已到期项前置并高亮
  - *tests/test_api.py（+）*
    - 补覆盖：提醒表/索引建库幂等、提醒 CRUD、`/api/news` 提醒摘要字段、stale item 删除后 reminder snapshot 保留
- **影响**：现在可以围绕“新闻里的未来事件”做应用内手动提醒，并在到期后回看关联新闻；本版涉及 `app.py` 与 schema，合入后需重启 Flask。

### 2026-06-20 — v1.9.6.12 improve: 收藏新闻功能
- **文件**
  - *schema.sql（+）*、*scanner.py（+）*、*app.py（+）*
    - `item_state` 新增独立 `favorite_at` 字段，收藏状态不再复用历史 `bookmarked`
    - 启动/测试建库链路补齐 `favorite_at` 幂等 migration，并兼容旧库里极少数 `bookmarked=1` 的一次性迁移
    - `PATCH /api/news/:id/state` 新增 `favorite` 开关；`/api/news`、`/api/news/:id/detail`、`/api/news/status`、`/api/sources` 同步支持 favorites 集合与 `favorite_at` 返回
  - *static/index.html（+）*、*static/app.js（+）*
    - 左侧与移动端集合入口新增“收藏”，新闻 row 与右栏详情新增星标收藏按钮
    - 收藏按钮接入现有 `icon-btn + applyIcon` 体系，选中态使用浅金色；在收藏集合内取消收藏后会立即刷新列表保持一致
    - 收藏集合默认按新闻时间新到旧排序，继续兼容 `sort_order=default|reverse`
  - *tests/test_api.py（+）*
    - 补覆盖：`favorite_at` migration、收藏状态增删、favorites 集合筛选/排序、`/api/news/status` 与详情/来源响应带出 `favorite_at`
- **影响**：现在可以把值得反复阅读的新闻单独收藏，且收藏与重要/稍后再看完全独立；本版涉及 `app.py` 和 schema，合入后需重启 Flask。

### 2026-06-19 — v1.9.6.11 improve: 新闻流时间排序切换
- **文件**
  - *app.py（+）*、*tests/test_api.py（+）*
    - `/api/news` 新增 `sort_order=default|reverse` 参数，支持新闻流类集合按默认/反向时间顺序切换
    - `feed + unread` 的 cursor 翻页条件改为跟随排序方向同步翻转，避免反向排序后重复、漏加载或假到底
    - 补覆盖：`feed + unread` 反向 cursor 分页，以及 `feed / important / read_later / notes / market_tags` 默认/反向排序
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 中栏工具区新增排序切换按钮，按当前集合显示 `旧→新` / `新→旧`
    - 切换排序时前端重置列表并重新请求第一页，不做本地 DOM 反转
    - 仅作用于 `feed / important / read_later / notes / market_tags`，不影响趋势页与搜索页
- **影响**：新闻流相关集合现在可以稳定切换时间方向；`feed + unread` 在正反向排序下都继续保持 cursor 翻页与自动已读语义一致。

### 2026-06-18 — v1.9.6.10 improve: 管理板块卡片网格布局优化
- **文件**
  - *static/app.js（+）*、*static/style.css（+）*、*static/index.html（+）*
    - 趋势页右栏“管理板块”改成紧凑卡片网格，默认仅展示板块名、关联新闻数、板块想法数，便于快速扫描定位
    - 新增“选中板块”统一操作面板，把重命名、合并、删除从逐行内嵌控件收束到单一区域
    - 删除区保留影响数量提示与二次确认；合并后稳定切到目标板块，删除后清空选中
- **影响**：趋势页管理板块默认态更适合浏览和定位，危险操作不再与普通编辑同权重混排，但 v1.9.6.9 的删除/合并后端语义保持不变。

### 2026-06-18 — v1.9.6.9 improve: 趋势板块支持删除与合并
- **文件**
  - *app.py（+）*、*schema.sql（+）*
    - 新增趋势板块影响统计、删除、合并 API
    - 删除板块时同步清理新闻关联和板块独立想法
    - 新增最小 deleted-key 抑制，仅用于防默认 seed 板块在删除后被自动补回
    - 合并板块时迁移新闻关联与趋势想法；若同一新闻已同时挂 source/target，则保留 target、跳过重复 source
  - *static/app.js（+）*、*static/style.css（+）*
    - 趋势页“管理板块”从“停用/启用”升级为“重命名 / 合并 / 删除”
    - 删除前弹出二次确认，并展示将解除的新闻关联数和将删除的板块想法数
  - *tests/test_api.py（+）*
    - 补覆盖：删除清理关联、默认板块删除后不回魂、合并迁移、重复关联去重、错误路径
- **影响**：趋势板块现在支持真正删除和合并；被删除板块不会继续显示在新闻 tag、趋势矩阵或板块详情中，默认板块删除后重启也不会自动恢复。

### 2026-06-16 — v1.9.6.8 improve: 优化设置页布局并显示版本号
- **文件**
  - *static/index.html（+34 −6）*
    - 设置页满屏显示，新增侧边细栏（图标入口）
    - 服务管理、模型管理、Release Notes 可通过侧栏切换
    - 标题旁新增版本号小字显示
  - *static/app.js（+45 −0）*
    - 新增设置页侧栏导航逻辑
  - *static/style.css（+91 −21）*
    - 满屏设置页布局、侧栏图标样式、版本号样式
- **影响**：设置页更大更易浏览，四大板块通过侧栏分区切换

### 2026-06-16 — v1.9.6.7 revert: 移除推荐功能并恢复 v1.9.6.6 行为
- **文件**：README.md、app.py、llm_client.py、scanner.py、schema.sql、static/app.js、static/index.html、static/style.css、tests/test_api.py
- 回退 v2.0.0 ~ v2.1.1.3 共 7 个推荐功能提交（9 files, +111 −5721）
- 影响：推荐集合、关键词库、candidate 审核等推荐功能全部移除

### 2026-06-12 — improve: 收敛 v1.9.6.5 设置页与 chatPage 信息密度
- **文件**
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 设置页移除常驻解释性副标题、模型用途提示、重启提醒与冗余 `当前使用` 长文案，只在读取/保存/失败时显示状态条
    - chatPage 移除 `归档（预留）` 与大段能力说明，标题下改为紧凑 `来源 + ● model` 状态展示
    - chatPage 复用正文已有 `key_points_zh`，在标题下以紧凑单行要点显示；无要点时自动隐藏，不再占空白
  - *static/app.js（+）*
    - fallback 来源判断改为优先读取 `ai.raw_json.provider` 前缀 `codex-fallback*`，兼容 structured fallback 使用真实 Codex model 的场景
    - DeepSeek 失败且 Codex body-only fallback 时显示“已由 GPT 完成翻译；结构化 fallback 失败，仅保留正文翻译”
    - DeepSeek 与 Codex fallback 都失败时，正文状态明确显示“DeepSeek 失败，Codex fallback 也失败”
- **影响**：设置页和 chatPage 的工具信息更紧凑；翻译链路一旦走 fallback，用户能更明确地区分 DeepSeek 主链路成功、GPT 结构化 fallback 成功和 body-only / 全失败场景。

### 2026-06-12 — fix: 修复 v1.9.6.3 设置页模型管理显示
- **文件**
  - *app.py（+）*、*static/app.js（+）*
    - Codex 模型目录改为直接使用 `codex debug models` 的原始 `name/slug` 作为下拉 label/value，不再做 `GPT/gpt` 美化或拼描述
    - 设置页模型下拉在保存后会保持当前已保存值；即使目录失败或当前值不在候选中，也会把已保存 model 回填到下拉并显示为当前使用
  - *tests/test_api.py（+）*
    - 更新 Codex 模型目录断言，覆盖 label/value 保持源 name、不拼描述
- **影响**：模型管理在保存后会立即显示可信的当前 model；Codex chat 模型下拉展示与 `codex debug models` 源返回保持一致。

### 2026-06-12 — improve: 重构 v1.9.6.2 设置页服务管理与模型管理
- **文件**
  - *app.py（+）*
    - `/api/settings` 新增 DeepSeek / Codex exec 轻量服务状态与模型目录返回
    - DeepSeek 模型优先读取官方 `GET /models`，失败自动 fallback 到默认候选，并保留已保存模型展示
    - Codex 模型改为解析本机 `codex debug models`，仅向前端暴露安全字段；同时补充 CLI / `codex exec` / models 可读状态
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 设置页文案改为“服务管理 / 模型管理”
    - DeepSeek / Codex 模型配置改为“下拉优先 + 自定义输入兜底”
    - 服务管理区展示 DeepSeek key、`/models` 可访问性、Codex CLI / exec / models 状态与 fallback 摘要
  - *tests/test_api.py（+）*
    - 覆盖 `/api/settings` 新字段、DeepSeek models 成功/失败 fallback、Codex models 解析成功/失败 fallback，以及 settings 响应不泄露 key
- **影响**：设置页现在能直接看到 DeepSeek 与 Codex exec 的轻量健康状态，并优先使用真实模型目录配置默认模型；即便目录读取失败，已保存模型仍可显示和继续保存。

### 2026-06-12 — feat: 新增 v1.9.6 codex exec chatPage MVP
- **文件**
  - *app.py（+）*、*settings.py（+）*
    - 恢复 `POST /api/news/:id/chat`，改为通过本机 `codex exec` 执行新闻提问
    - 首问从 `thread.started.thread_id` 提取具体 session id，续问固定使用 `codex exec resume <session_id>`，不使用 `--last`
    - 新增 `llm.codex_chat.model` 设置项；留空时走 Codex 默认模型
    - 对 `detail_not_ready / provider_busy / provider_timeout / session_invalid / missing_session_id / provider_failed` 返回清晰结构化错误
  - *static/index.html（+）*、*static/app.js（+）*
    - 右侧 chatPage 改为单一 `Codex exec` 入口，不再展示 provider 选择
    - 设置页新增 `Codex Chat 模型` 输入项；切换模型时清空当前新闻的临时对话并重新建 session
    - 同一条新闻支持前端内存态多轮对话；切换新闻即清空
  - *tests/test_api.py（+）*
    - 覆盖首问上下文透传、session id 返回、显式 resume、禁止 `--last`、模型设置生效、错误码与旧配置兼容
- **影响**：用户现在可以在正文 ready 的新闻详情里直接通过 `codex exec` 提问；同一新闻支持多轮对话，且每轮都绑定具体 session id。当前版本仍不做 chat 落库、归档或翻译保底替换。

### 2026-06-12 — improve: 收敛 v1.9.5.2 设置页 LLM 配置
- **文件**
  - *app.py（+）*、*settings.py（+）*
    - `/api/settings` 只保留 DeepSeek API 状态与翻译 / 总结模型配置
    - 兼容忽略旧配置中的 `llm.chat` / `providers.openai` 历史字段，不因旧配置报错
    - `chat_providers` 退场，现阶段不再把 DeepSeek / ChatGPT 作为 chatPage 的 API provider 暴露
  - *static/index.html（+）*、*static/app.js（+）*
    - 设置页 `LLM API 管理` 仅保留 DeepSeek key 管理入口
    - `模型与功能路由` 区收敛为 DeepSeek 翻译 / 总结模型配置，并明确文案“不用于 chatPage”
    - chatPage 保留占位，但不再展示可配置 API provider
  - *tests/test_api.py（+）*
    - 覆盖旧配置兼容、DeepSeek-only 设置保存、chat API 退场与设置页收敛
- **影响**：设置页现在只呈现仍会继续保留的 DeepSeek 配置；API chat provider 已从当前版本的设置与正文详情中退场，后续 chatPage 将另走 `codex exec` 方向。

### 2026-06-11 — feat: 新增 v1.9.5.1 设置页 API Key 管理
- **文件**
  - *secret_store.py（新文件）*、*app.py（+）*、*llm_client.py（+）*
    - 新增 macOS Keychain secret store，统一管理 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`
    - 设置页新增 `PUT/DELETE /api/settings/secrets/:provider`，支持 DeepSeek / ChatGPT key 新增、更新、删除
    - `/api/settings` 与 chat provider 状态继续只返回 `configured` 布尔值，不回显任何 key 明文
    - LLM 调用链在环境变量缺失时可自动回退读取 Keychain
  - *static/index.html（+）*、*static/app.js（+）*、*static/style.css（+）*
    - 设置页 `LLM API 管理` 区新增每个 provider 的 password 输入、保存/更新、删除与确认交互
    - 保存/删除后刷新状态，并明确提示“重启 Flask 后生效”
  - *tests/test_api.py（+）*、*tests/test_llm_client.py（+）*
    - 覆盖 key save/delete、非法 provider、空 key、失败不泄露、Keychain 回退读取
- **影响**：用户现在可以直接在设置页安全管理 DeepSeek / ChatGPT API key，key 只存 macOS Keychain，不会写入配置文件、数据库或前端存储。

### 2026-06-11 — feat: 新增 v1.9.4 设置页 MVP
- **文件**
  - *app.py（+189 −0）*、*settings.py（+74 −0）*、*llm_client.py（+16 −2）*
    - 新增 `GET/PUT /api/settings`，以本机轻量配置文件保存 LLM 路由设置
    - 新增 `GET /api/release-notes`，稳健解析 README `What's Changed` 为版本记录
    - 设置页只返回 API key `configured` 布尔状态，不回显明文
    - 翻译 / 总结支持配置 DeepSeek model；chat 支持默认 provider 与 OpenAI/DeepSeek 各自 model
    - 新配置会被 chat 与翻译链路消费；新请求通常立即生效，worker 完全一致时仍建议重启 Flask
  - *static/index.html（+67 −1）*、*static/app.js（+255 −0）*、*static/style.css（+257 −0）*
    - 顶栏新增 `setting` 按钮，桌面/手机统一从这里打开设置页
    - 设置页采用 overlay 方式打开，关闭后不污染当前新闻流、搜索、趋势或正文状态
    - 页面内新增三块：`Release Notes`、`LLM API 状态`、`模型与功能路由配置`
    - `Release Notes` 目前按 README 展示版本分组，并区分 `NEW / IMPROVE / FIX`
  - *tests/test_api.py（+177 −0）*
    - 覆盖 release notes 接口、设置读写与无 key 泄露、chat/翻译模型路由实际生效
- **影响**：用户现在可以从顶栏直接打开设置页，查看版本发布记录、确认 DeepSeek/ChatGPT key 是否已配置，并调整翻译/总结与 chat 的默认模型/路由，而不需要修改前端代码或暴露 API key 明文。

### 2026-06-11 — feat: 新增 v1.9.3 右栏新闻提问 MVP
- **文件**
  - *app.py（+117 −0）*
    - `GET /api/news/:id/detail` 新增 `chat_providers`，返回 `DeepSeek / ChatGPT` 可用性与能力提示
    - 新增无状态 `POST /api/news/:id/chat`
    - 仅在正文已就绪时允许提问；支持 `provider_busy / detail_not_ready / missing_*_api_key / provider_timeout / provider_failed` 等清晰错误
  - *llm_client.py（+141 −0）*
    - 新增 `ask_deepseek_news_chat()` 与 `ask_openai_news_chat()`
    - DeepSeek 走稳定 API 对话；ChatGPT 走 OpenAI Responses API，并启用 `web_search`
    - Prompt 明确要求区分“正文事实 / 外部补充 / 推断”，且最新进展无法确认时必须直说
  - *static/index.html（+22 −2）*、*static/app.js（+175 −0）*、*static/style.css（+58 −0）*
    - 详情右栏新增 `提问` 入口与 panel 内 chatPage 子视图，不新开页面
    - 支持切换 `DeepSeek / ChatGPT`，并明确显示两者能力差异
    - 对话仅存在当前前端内存；切换新闻或切换模型即清空，并预留禁用态 `归档（预留）`
  - *tests/test_api.py（+178 −0）*
    - 覆盖 provider 可用性透出、正文未就绪拒绝提问、DeepSeek/OpenAI 路由透传、缺 key 与 busy 冲突分支
- **影响**：用户现在可以在右侧正文详情里直接围绕当前新闻发问。`ChatGPT` 可尝试联网补充最新公开信息；`DeepSeek` 则只承诺基于正文与已有知识回答，不承诺实时搜索。

### 2026-06-10 — fix: 调整新闻流与稍后阅读为全局旧到新排序
- **文件**
  - *app.py（+2 −2）*
    - `feed` 排序改为日期 `旧 → 新`、同日内 `旧 → 新`
    - `read_later` 同步改为日期 `旧 → 新`、同日内 `旧 → 新`
    - `feed + unread` 的 cursor/anchor 比较方向同步改成适配新排序的“严格晚于当前 cursor”
  - *tests/test_api.py（+47 −3）*
    - 更新 `feed` 跨日期排序回归测试为旧→新预期
    - 新增 `read_later` 跨日期旧→新回归测试
    - 更新 reading checkpoint locate 预期，确保“回到上次阅读”仍符合新的 feed 顺序
- **影响**：`feed` 和 `read_later` 现在都按全局时间线从旧到新阅读，跨日期时不再把前日新闻放到今日新闻之后；`important / notes / market_tags / search / trends` 排序保持不变。

### 2026-06-10 — fix: 修复仅未读新闻流分页漏读
- **文件**
  - *app.py（+103 −5）*
    - 为 `collection=feed & read_filter=unread` 新增 cursor/anchor 分页路径
    - cursor 基于 `date DESC + published_at ASC + id ASC` 的 feed 稳定排序
    - 下一页改为按 anchor 条件取“当前位置之后”的未读新闻，不再依赖动态未读集合上的 `OFFSET`
    - 返回 `has_more` 与 `next_cursor`，只在目标场景启用，非目标集合继续保留原分页逻辑
  - *static/app.js（+15 −0）*
    - 新增 `state.feedUnreadCursor`
    - `feed + unread` 模式下，`loadFirstPage/loadNextPage` 改为消费后端 cursor
    - 切换集合、切换已读筛选、切换来源或刷新列表时重置 cursor
  - *tests/test_api.py（+74 −0）*
    - 新增回归测试：加载第一页后先把部分 row 标已读，再请求下一页，断言后续未读不会被跳过
    - 覆盖 `source_filter` 场景，确认已加载 row 批量已读后刷新不会再冒出之前漏掉的未读
- **影响**：`新闻流 + 仅未读` 现在不会因为“滚过即已读”导致未读结果集动态收缩、进而让后续 `OFFSET` 分页漏项；滚过顶部逐条已读、到底 5 秒后仅标当前已加载 row 已读的原语义保持不变。

### 2026-06-07 — fix: 调整搜索页视觉布局
- **文件**
  - *static/index.html（+5 −4）*
    - 移除搜索页内的 `搜索` title 与说明副标题
    - 保持搜索页为两行：第一行 `搜索框 + 搜索按钮`，第二行 `范围 + 时间`
  - *static/style.css（+14 −26）*
    - 移除搜索页专属边框、背景和标题区样式
    - 搜索页条件区恢复为更接近普通内容区的轻量布局
    - 保持桌面/手机下两行搜索控件布局稳定
  - *static/app.js（+4 −0）*
    - `执行搜索` 按钮最终改为 **“搜索”文本**
    - 搜索页其它 v1.9.1 语义与交互不变
- **影响**：搜索页视觉更简洁，去掉了独立标题、说明和专属背景色；页面仍保留 v1.9.1 的独立搜索语义，只对搜索条件区做了最小可读性调整。

### 2026-06-07 — feat: 新增独立搜索页与基础筛选
- **文件**
  - *app.py（+48 −0）*
    - 扩展 `GET /api/search`，新增 `range`、`time` 参数
    - 支持范围 `all / important / notes / market_tags / detail_ready`
    - 支持时间 `all / today / 7d / 30d`
    - 搜索结果固定 recent（发布时间新→旧）
  - *static/app.js（+218 −133）*
    - 把旧顶栏临时搜索模式改成独立 `search` collection
    - 搜索页仅保留 `关键词 / 范围 / 时间` 三个条件
    - 搜索页不再继承或恢复原集合 / 来源 / 已读筛选状态
    - 搜索结果仍复用新闻 row 与右侧正文详情链路
  - *static/index.html（+33 −0）*
    - 桌面左侧栏新增 `搜索` 入口
    - 手机集合面板新增 `搜索`
    - 新增搜索页自己的输入框、范围和时间筛选控件
  - *static/style.css（+81 −0）*
    - 新增独立搜索页条件区样式，适配桌面与手机布局
  - *tests/test_api.py（+104 −0）*
    - 新增 `range/time` 搜索测试，并覆盖搜索忽略 `collection/source_filter/read_filter` 的独立页语义
- **影响**：搜索现在是 app 内的独立页面，而不是顶栏临时过滤器。搜索页只使用自己的关键词、范围和时间条件；用户离开搜索页时通过主动点击其他集合或趋势页切换，不再恢复“进入搜索前现场”。

### 2026-06-07 — fix: 修复桌面端搜索框展开布局
- **文件**
  - *static/index.html（+2 −2）*
    - 更新 `style.css` / `app.js` 版本参数到 `?v=1.9.0.2`，避免桌面端继续命中旧缓存
  - *static/style.css（+15 −5）*
    - 仅桌面端把顶栏搜索条改为绝对定位居中展开，脱离 topbar 文档流
    - 限制桌面搜索条宽度与可用空间，避免与右侧铃铛、搜索按钮重叠
    - 在移动端 media 中显式 reset 为 `position: static`，保持手机端当前满意布局不变
- **影响**：桌面端点击搜索按钮后，搜索框会在顶栏中间稳定展开，外观/字体控件、搜索按钮、错误统计铃铛都不再位移或重叠；手机端搜索与铃铛布局保持 v1.9.0.1 现状。

### 2026-06-07 — fix: 统一桌面与手机端搜索按钮交互并修复铃铛位置
- **文件**
  - *static/index.html（+22 −0）*
    - 顶栏结构改为 `标题区 + 搜索按钮 + 铃铛` 的统一布局
    - 移除搜索框旁边的独立关闭按钮，改为由同一个搜索按钮承担开关
  - *static/app.js（+58 −0）*
    - 新增统一的搜索按钮开关逻辑，桌面/手机都改为默认折叠搜索条
    - 执行搜索后再次点击搜索按钮也会退出搜索模式并收起搜索条
    - 保留现有 `/api/search` 结果模式与退出后恢复原列表状态，不改数据逻辑
  - *static/style.css（+90 −21）*
    - 桌面端铃铛重新锚定到顶栏右侧安全区域，error 弹层不再跑到屏幕外
    - 手机端搜索条默认折叠，展开后仅占一行；桌面端同样切换为按钮展开搜索条
    - 统一桌面/手机搜索入口样式，压缩顶栏占位
- **影响**：顶栏搜索交互现在在桌面和手机端保持一致，默认只显示搜索按钮；再次点击即可收起，执行搜索后也能收起。桌面端铃铛和 error 面板位置恢复正常，手机端顶栏不再被常驻搜索框撑高。

### 2026-06-07 — feat: 新增全局全文搜索 MVP
- **文件**
  - *app.py（+119 −0）*
    - 提取 `serialize_news_rows()` 复用新闻 row 字段组装逻辑
    - 新增 `GET /api/search`，基于现有表 `LEFT JOIN + LIKE` 做全局全文搜索
    - 覆盖标题、摘要、来源、英文正文、AI 中文正文/要点/结论、新闻想法、板块 tag / display_name
    - 搜索结果使用 `SELECT DISTINCT / COUNT(DISTINCT)` 去重，并复用现有新闻 row 结构返回
  - *static/index.html（+5 −0）*
    - 顶栏新增全局搜索输入框、搜索按钮、关闭按钮
  - *static/app.js（+192 −0）*
    - 新增搜索模式状态、进入/退出搜索逻辑、搜索结果分页加载
    - 搜索模式下复用现有新闻 row / 正文详情链路
    - 关闭搜索后恢复进入搜索前的集合、仅读筛选、来源筛选与手机趋势来时集合状态
    - 搜索模式下隐藏来源筛选、仅读筛选、批量操作与趋势专属入口
  - *static/style.css（+65 −0）*
    - 新增顶栏搜索区域样式，并适配桌面/手机布局
  - *tests/test_api.py（+132 −0）*
    - 新增全局搜索测试，覆盖标题、英文正文、AI 中文正文/要点、新闻想法、板块 tag、去重、空关键词与无结果空态
- **影响**：现在可以从顶栏直接做全局全文搜索，结果跨集合覆盖新闻标题、原文、AI 中文、想法与板块标签；搜索结果仍然使用原有新闻 row 与正文详情体验，退出搜索后会回到进入搜索前的阅读上下文

### 2026-06-07 — feat: 隐藏无摘要并新增错误统计铃铛
- **文件**
  - *app.py（+62 −0）*
    - 新增 `GET /api/error-stats`，只读取当日 `dailyFreshNews_YYYY-MM-DD.md` 的 `## errors` 区块
    - 后端聚合改为“时间块 → source error 列表”结构，贴近铃铛面板展示
  - *parser.py（+44 −0）*
    - 新增 `parse_daily_errors()`，专门解析 `dailyFreshNews` 中的 `errors` 区块
  - *static/app.js（+94 −1）*
    - 顶栏新增铃铛按钮交互与错误统计面板渲染
    - 趋势右侧新闻卡片摘要为空时，彻底隐藏摘要区域，不再显示“无摘要”
  - *static/index.html（+6 −0）*
    - 顶栏增加铃铛按钮与错误统计面板容器
  - *static/style.css（+61 −0）*
    - 新增铃铛面板、错误分组与空态样式
  - *tests/test_api.py（+38 −0）*
    - 覆盖 error stats 的“无文件空态 / 读取 dailyFreshNews errors 成功”两种情况
- **影响**：应用内不再出现“无摘要”占位；顶栏铃铛可直接查看当日 `dailyFreshNews` 记录下来的采集 error，且展示更适合按某一轮失败时间排查问题

### 2026-06-06 — feat: 趋势新闻改为打开应用内正文
- **文件**
  - *static/app.js（+83 −10）*
    - 趋势右侧新闻卡片标题/主区域点击改为复用正文详情打开逻辑
    - 新增 `detailReturnToTrend` 状态，支持从正文详情返回刚才的趋势明细
    - 普通新闻 row 也改为复用 `openItemDetail()`，消除重复打开逻辑
  - *static/index.html（+1 −0）*
    - 正文详情新增“返回趋势明细”按钮容器
  - *static/style.css（+31 −0）*
    - 新增趋势新闻卡片可点击态、标题按钮、原文小外链与“返回趋势明细”按钮样式
- **影响**：趋势页点击新闻时不再直接跳出到原站，而是先进入应用内正文详情；用户仍可打开原文，并能从正文顺畅回到刚才的趋势明细

### 2026-06-06 — feat: 正文页标签与趋势卡片展示微调
- **文件**
  - *static/index.html（+1 −4）*
    - 正文页板块标签容器改到标题下方 inline 展示
    - 移除旧的“板块标签”标题与卡片框结构
  - *static/app.js（+19 −12）*
    - 详情页标签渲染切换到 `detailInlineMarketTags`
    - 趋势右侧新闻卡片移除单一垃圾桶，改成每个板块 tag chip 自带 `×` 删除
  - *static/style.css（+24 −20）*
    - 新增正文页 inline 标签容器样式
    - “我的想法”正文显示统一为蓝色
    - 趋势卡片 tag chip 补充内置删除按钮样式
- **影响**：正文页标题区更紧凑；趋势右侧栏一条新闻有多个板块 tag 时，现在可以直接在对应 chip 上逐个移除，交互与正文页保持一致

### 2026-06-06 — fix: 手机趋势页返回来时集合
- **文件**
  - *static/app.js（+5 −1）*
    - 新增 `lastNewsCollectionBeforeTrends` 记录手机端进入趋势前的新闻集合
    - 从 `trends` 点击底部 `新闻流` tab 时，返回来时集合而不是固定回 `feed`
    - 趋势页下该 tab 的文案也同步显示来时集合名，避免“功能正确但文案仍写死为新闻流”
- **影响**：手机端 `重要 / 稍后 / 想法 / 板块 / 新闻流 → 趋势 → 新闻流` 现在都会回到来时集合，交互心智一致

### 2026-06-06 — feat: 新闻列表与趋势明细支持想法预览
- **文件**
  - *app.py（+14 −0）*
    - 新增 `build_note_preview()`，统一生成紧凑截断的想法预览文本
    - `/api/news`、`/api/market-trends/detail`、`/api/market-trends/tag-detail` 新增 `note_preview`
    - `PUT /api/news/:id/note` 保存响应同步返回最新 `note_preview`
  - *static/app.js（+29 −2）*
    - 普通新闻列表 row 新增浅蓝色想法预览
    - 趋势右侧明细新闻卡片同样显示想法预览
    - 保存/清空正文想法后，本地同步 `note_preview` 与 row UI
  - *static/style.css（+16 −0）*
    - 新增 `row-note-preview / trend-detail-note-preview` 浅蓝样式，限制最多 2 行
    - 补充 light / dark / system dark 变量
  - *tests/test_api.py（+3 −0）*
    - 验证 `note_preview` 在保存、列表展示、清空后保持一致
- **影响**：用户现在可以直接在各集合新闻 row 和趋势明细新闻卡片中看到简短想法预览，无需先进入正文页

### 2026-06-06 — feat: 右侧栏想法输入区顶部化
- **文件**
  - *static/index.html（+9 −7）*
    - 将“写想法 / 编辑想法”输入区从正文滚动区内移到顶部操作区下方
  - *static/app.js（+2 −0）*
    - 写想法区与板块选择区改为互斥显示，避免顶部同时展开两个输入区
  - *static/style.css（+9 −0）*
    - 为顶部想法输入区补充独立容器与标题样式
- **影响**：详情页右侧栏的想法输入区现在与板块选择区属于同一顶部区域，不再随正文一起滚动，阅读流更稳定

### 2026-06-06 — feat: 趋势强调色与日期 section 数量联动
- **文件**
  - *app.py（+18 −0）*
    - `/api/news` 新增 `date_counts`
    - 按当前 `collection + read_filter + source_filter + q` 返回每个 `date_key` 的真实数量
  - *static/app.js（+68 −2）*
    - 普通新闻列表日期 section 右侧新增数量显示，覆盖 `feed / important / read_later / notes / market_tags`
    - 当前集合成员资格发生本地变化时，日期数量实时联动：已读、取消重要、取消稍后阅读、清空想法、删除最后一个板块 tag 都会同步递减
    - 趋势单元格中“有新闻想法”与“仅趋势想法”的 bullish/bearish chip 统一走强调色
  - *static/style.css（+25 −2）*
    - 新增趋势强调色变量，保持 light / dark / system dark 可读
    - 日期 section 调整为左右布局并补充数量样式
  - *tests/test_api.py（+57 −0）*
    - 新增 `date_counts` 覆盖：同日多条、跨日期、`feed unread/all`、`important all`
    - 验证 `mark-read-by-ids` 只影响 `unread` 计数，不影响 `all` 总数
- **影响**：趋势页有想法的信号更醒目；新闻列表各集合的日期 section 现在显示真实条数，并在 row 离开当前集合/筛选结果时实时同步

### 2026-06-06 — fix: 自动到底已读仅标记当前已加载新闻
- **文件**
  - *app.py（+32 −0）*
    - 新增 `POST /api/news/mark-read-by-ids`
    - 将“按 ids 批量标读”和“当前筛选全集标读”彻底分离
  - *static/app.js（+15 −3）*
    - 新闻流到底 5 秒自动已读改为仅上传当前已加载 `item_ids`
    - 前端本地已读同步也只作用于当前已加载 row
  - *tests/test_api.py（+38 −0）*
    - 新增 `mark-read-by-ids` 回归测试
    - 覆盖“只标传入 ids，不误伤同筛选范围未加载新闻”语义
- **影响**：新闻流到底自动已读不再误标后台新入库但用户尚未刷新/加载的未读新闻；手动“全部标已读”继续保留跨页全量语义

### 2026-06-05 — feat: 趋势集合支持多条想法与交互增强
- **文件**
  - *app.py（+191 −44）*
    - `migrate_market_trend_notes()`：将 `market_trend_notes` 从“一格一条”迁移为“一格多条”，保留旧数据
    - 趋势接口改为返回 `trend_notes[]`，并补充趋势想法多条计数与“有新闻想法”颜色增强所需字段
    - 新增趋势想法按 `id` 编辑/删除接口
  - *schema.sql（+1 −2）*
    - 移除 `market_trend_notes(date_key, tag, direction)` 唯一约束
  - *static/app.js（+205 −101）*
    - 趋势表头支持二次点击收起右栏
    - 趋势明细新闻卡片新增“移除板块”按钮，删除后矩阵与明细同步刷新
    - 趋势想法改为多条独立展示，并分离“新建 / 编辑 / 删除”
    - 有新闻想法的趋势信号使用更鲜艳的红/绿样式
  - *static/style.css（+18 −9）*
    - 补充趋势卡片头部按钮与增强态 chip 样式
  - *tests/test_api.py（+24 −8）*
    - 覆盖多条趋势想法、新接口、计数更新与删除路径
- **影响**：趋势页现在支持一格多条想法，且趋势总览 / 单元格明细 / 删除板块标签后的矩阵刷新都已打通

### 2026-06-05 — feat: 新增副标题并调整稍后阅读排序为旧→新
- **文件**
  - *app.py（+1 −1）*
    - `news_order_by_sql`：`read_later` 集合排序改为与 `feed` 一致（日期内旧→新）
  - *static/index.html（+4 −1）*
    - topbar 新增副标题「如果是牛市，那么永远不缺机会。」
  - *static/style.css（+12 −0）*
    - 新增 `.topbar-brand` / `.topbar-subtitle` 样式
  - *tests/test_api.py（+7 −0）*
    - 排序测试扩展：验证 `read_later` 集合日内旧→新
- **影响**：顶部展示副标题；稍后阅读按时间发展顺序排列

### 2026-06-05 — feat: 新增 Gemini 保底翻译
- **文件**
  - *app.py（+11 −2）*
    - `process_pending_ai_once`：DeepSeek 失败后自动调用 Gemini 保底翻译
  - *llm_client.py（+100 −0）*
    - 新增 `generate_gemini_fallback_translation()`，通过 `opencli gemini ask` 执行翻译
    - 新增 `_extract_gemini_translation()` 清理 opencli 噪声与 Choice A/B 选择
  - *static/app.js（+10 −5）*
    - Gemini 保底翻译标识：状态栏显示「Gemini 保底翻译，结果可能不稳定」
    - 保底翻译不显示要点/结论区块
  - *tests/test_api.py（+142 −0）*
    - 新增 Gemini 保底成功 + 两级均失败测试
- **影响**：DeepSeek 不可用时自动切换 Gemini 保底，避免翻译静默失败

### 2026-06-03 — feat: 增加趋势板块表头下钻总览
- **文件**
  - *app.py（+99 −0）*
    - 新增 `GET /api/market-trends/tag-detail` 端点，按板块标签列出所有相关新闻及趋势笔记
  - *static/app.js（+157 −48）*
    - 趋势页板块表头可点击下钻，展示该板块完整新闻列表与趋势笔记
  - *static/style.css（+36 −0）*
    - 下钻详情页样式
  - *tests/test_api.py（+63 −0）*
    - 新增 tag-detail 端点测试
- **影响**：趋势页板块可下钻查看完整新闻列表

### 2026-06-03 — feat: 新增趋势单元格想法与手动信号
- **文件**
  - *app.py（+185 −6）*
    - 新增趋势单元格想法 CRUD API 与手动多空信号端点
  - *schema.sql（+11 −0）*
    - 新增 `trend_thoughts` 表
  - *static/app.js（+379 −43）*
    - 趋势页每个单元格支持添加想法与手动多空信号
  - *static/index.html（+42 −0）*
    - 新增手动信号按钮节点
  - *static/style.css（+12 −0）*
    - 手动信号按钮样式
  - *tests/test_api.py（+67 −0）*
    - 新增趋势想法与信号测试
- **影响**：趋势页可记录个人判断与手动信号

### 2026-06-02 — feat: 新增自定义板块标签管理
- **文件**
  - *app.py（+211 −21）*
    - 新增 `sector_tags` 表 CRUD API
  - *schema.sql（+9 −0）*
    - 新增 `sector_tags` 表
  - *static/app.js（+193 −15）*
    - 新增板块标签管理面板
  - *static/index.html（+14 −0）*
    - 新增标签管理面板 DOM
  - *static/style.css（+59 −0）*
    - 标签管理面板样式
  - *tests/test_api.py（+74 −0）*
    - 新增板块标签 CRUD 测试
- **影响**：用户可自定义板块标签

### 2026-06-02 — feat: 扩充板块标签选项
- **文件**
  - *app.py（+2 −0）*
    - 板块标签选项扩充
  - *static/app.js（+1 −1）*
    - 前端标签列表同步
- **影响**：板块标签选项更丰富

### 2026-06-02 — feat: 优化手机端新闻流入口交互
- **文件**
  - *static/app.js（+6 −2）*
    - 手机端新闻流入口交互优化
- **影响**：手机端新闻流入口更顺畅

### 2026-06-02 — feat: 新增手机端趋势底部入口
- **文件**
  - *static/app.js（+12 −3）*
    - 底部导航新增趋势入口
  - *static/index.html（+1 −0）*
    - 新增趋势底部按钮节点
  - *static/style.css（+3 −3）*
    - 底部 tab 样式适配
- **影响**：手机端可快速进入趋势页

### 2026-06-02 — feat: 按集合区分新闻排序规则
- **文件**
  - *app.py（+14 −3）*
    - feed/important/read_later 集合使用不同排序逻辑
  - *tests/test_api.py（+38 −0）*
    - 新增各集合排序验证测试
- **影响**：各集合按各自逻辑排列

### 2026-06-02 — feat: 按板块方向着色新闻标题
- **文件**
  - *static/app.js（+17 −0）*
    - 新闻标题按看多/看空方向动态着色
  - *static/style.css（+28 −0）*
    - 板块方向颜色变量
- **影响**：新闻标题颜色反映板块方向

### 2026-06-02 — fix: 优化趋势页布局与交互细节
- **文件**
  - *static/app.js（+3 −0）*
    - 趋势页交互微调
  - *static/index.html（+2 −2）*
    - 趋势页 DOM 调整
  - *static/style.css（+55 −2）*
    - 趋势页布局优化
- **影响**：趋势页更整洁

### 2026-06-02 — feat: 新增趋势页面 MVP
- **文件**
  - *app.py（+183 −0）*
    - 新增 `/api/trends` 端点，按板块聚合新闻密度与方向
  - *static/app.js（+268 −4）*
    - 新增趋势页前端，按板块展示新闻密度与方向
  - *static/index.html（+12 −1）*
    - 新增趋势页 DOM 结构
  - *static/style.css（+254 −0）*
    - 趋势页完整样式
  - *tests/test_api.py（+67 −0）*
    - 新增趋势 API 测试
- **影响**：可从导航进入趋势页面查看板块热度与方向

### 2026-06-02 — feat: 恢复新闻流到底自动已读但保留当前列表
- **文件**
  - *static/app.js（+89 −0）*
    - 滚到底自动已读恢复，但不再刷新列表
- **影响**：滚动到底自动标已读但不打断阅读

### 2026-06-01 — fix: 修复新闻流滑出顶部自动已读失效
- **文件**
  - *static/app.js（+37 −6）*
    - 修复 IntersectionObserver 参照系导致滑出顶部自动已读失效
- **影响**：滑出顶部自动已读恢复正常

### 2026-06-01 — feat: 完成 v1.8.2.1 板块交互小修并撤回自动已读
- **文件**
  - *app.py（+23 −0）*
    - 板块标签交互后端适配
  - *static/app.js（+13 −0）*
    - 板块标签交互优化
  - *static/index.html（+4 −4）*
    - 板块标签 UI 调整
  - *static/style.css（+1 −2）*
    - 板块标签样式微调
  - *tests/test_api.py（+6 −0）*
    - 板块标签测试补充
- **影响**：板块标签交互更稳定

### 2026-06-01 — feat: 实现 v1.8.2 板块标签与看多看空标记
- **文件**
  - *app.py（+145 −0）*
    - 新增 sector_tags 与 sentiment（看多/看空/中性）标记 API
  - *schema.sql（+9 −0）*
    - 新增 sentiment 字段
  - *static/app.js（+170 −2）*
    - 新增板块标签选择器与看多/看空标记交互
  - *static/index.html（+11 −0）*
    - 新增板块标签与方向标记 DOM
  - *static/style.css（+111 −0）*
    - 板块标签与方向标记样式
  - *tests/test_api.py（+97 −0）*
    - 新增板块标签与 sentiment 测试
- **影响**：新闻可标记板块与看多/看空方向

### 2026-06-01 — feat: 实现 v1.8.1 想法集合与右栏操作按钮整理
- **文件**
  - *app.py（+6 −0）*
    - 想法集合查询适配
  - *static/app.js（+24 −4）*
    - 新增想法集合入口，右栏操作按钮整理
  - *static/index.html（+3 −1）*
    - 右栏按钮布局调整
  - *static/style.css（+8 −0）*
    - 按钮样式适配
  - *tests/test_api.py（+56 −0）*
    - 新增想法集合测试
- **影响**：想法集合入口 + 右栏按钮更清晰

### 2026-06-01 — feat: 实现 v1.8.0 新闻级我的想法基础功能
- **文件**
  - *app.py（+63 −0）*
    - 新增 my_thoughts CRUD API（GET/POST/PUT/DELETE）
  - *schema.sql（+7 −0）*
    - 新增 `my_thoughts` 表
  - *static/app.js（+100 −0）*
    - 右栏新增想法编辑区
  - *static/index.html（+12 −0）*
    - 新增想法编辑 DOM
  - *static/style.css（+73 −0）*
    - 想法编辑区样式
  - *tests/test_api.py（+57 −0）*
    - 新增 my_thoughts CRUD 测试
- **影响**：每条新闻可记录个人想法

### 2026-06-01 — fix: 调整新闻流默认筛选为仅未读
- **文件**
  - *static/app.js（+2 −2）*
    - 新闻流默认 read_filter 从 all 改为 unread
- **影响**：打开默认仅显示未读新闻

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
