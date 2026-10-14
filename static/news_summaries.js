/* Private history and snapshot catch-up UI. Never renders model HTML or marks news optimistically. */
(() => {
  const $ = (id) => document.getElementById(id);
  const dialog = $("newsSummariesDialog");
  if (!dialog) return;
  let token = "", active = null, entries = [], selected = "", generation = 0, timer = null, busy = false, totalRecords = 0, bindingVersion = 0, historyRequest = 0;
  const status = $("newsSummaryProgress"), list = $("newsSummaryList"), content = $("newsSummaryContent");
  const watched = new Set(), completed = new Set();
  const running = (job) => job && ["pending", "generating", "checking"].includes(job.status);
  const make = (tag, text = "") => { const e = document.createElement(tag); e.textContent = text; return e; };
  function requestUUID() {
    const c = globalThis.crypto;
    if (typeof c?.randomUUID === "function") return c.randomUUID();
    if (typeof c?.getRandomValues !== "function") throw new Error("浏览器不支持安全随机数生成，无法创建请求标识；请更新浏览器后重试");
    // getRandomValues is available on HTTP; construct an RFC 4122 version-4 UUID.
    const bytes = c.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  async function api(path, options = {}) {
    const r = await fetch(path, { cache: "no-store", ...options });
    const x = await r.json();
    if (!r.ok || !x.ok) { const e = new Error(x.message || x.error || "请求失败"); e.code = x.error; throw e; }
    return x;
  }
  function controls() {
    $("startNewsSummary").disabled = busy || running(active);
    $("summarizeUnreadBtn").disabled = busy || running(active);
    $("cancelNewsSummary").classList.toggle("hidden", !running(active));
    $("cancelNewsSummary").disabled = busy || !!active?.cancel_requested;
  }
  function showJob(job) {
    if (active?.id !== job?.id || active?.status !== job?.status || active?.cancel_requested !== job?.cancel_requested) bindingVersion++;
    active = job;
    const labels = { pending: "已锁定未读，准备生成", generating: "正在生成新闻补课", checking: "正在自动核对事实、日期与引用", completed: "总结已保存，可回看；仅本批新闻已标读", failed: "任务失败，未清除本批未读", cancelled: "已取消，未清除本批未读" };
    status.textContent = job ? `${labels[job.status] || job.status} · ${job.start_date} → ${job.end_date} · ${job.item_count} 条${job.cancel_requested && running(job) ? " · 正在停止并回收运行进程" : ""}${job.message ? "。" + job.message : ""}` : "成功生成并保存可读取结果后，才标记点击时这一批已读；新到新闻不受影响。";
    if (job?.scope) status.textContent += "\n" + scopeText(job.scope);
    controls();
  }
  function renderList(total) {
    list.replaceChildren();
    entries.forEach((row) => {
      const b = make("button", `${row.start_date} → ${row.end_date}\n${row.item_count} 条 · ${row.created_at.replace("T", " ")}`);
      b.className = "summary-history-item"; b.classList.toggle("active", row.id === selected);
      b.addEventListener("click", () => openDetail(row.id)); list.appendChild(b);
    });
    if (!entries.length) list.appendChild(make("p", "尚无成功保存的新闻总结。"));
    $("moreNewsSummaries").classList.toggle("hidden", entries.length >= total);
  }
  function inline(text, host, sources) {
    const regex = /(\[\[(N\d{4,})\]\]|\*\*([^*]+)\*\*)/g;
    let last = 0, m;
    while ((m = regex.exec(text))) {
      host.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[2] && sources.has(m[2])) {
        const b = make("button", `[${m[2]}]`); b.className = "summary-citation";
        const ref = m[2], i = sources.get(ref); b.title = `${i.date || "报道日期不明"} · ${i.source_name || i.source} · ${i.title}`;
        b.addEventListener("click", () => {
          const target = content.querySelector(`[data-summary-ref="${ref}"]`);
          if (target) { target.parentElement.open = true; target.scrollIntoView({ block: "center" }); target.focus({ preventScroll: true }); }
        }); host.appendChild(b);
      } else host.appendChild(make("strong", m[3] || m[0]));
      last = regex.lastIndex;
    }
    host.appendChild(document.createTextNode(text.slice(last)));
  }
  async function openDetail(id) {
    const current = generation, dbToken = token; selected = id;
    try {
      const x = await api(`/api/news-summaries/${encodeURIComponent(id)}`);
      if (current !== generation || dbToken !== token || x.summary.database_token !== token || selected !== id) return;
      const s = x.summary, sources = new Map(s.sources.map(i => [i.ref, i]));
      content.replaceChildren(make("h2", s.title));
      content.appendChild(make("p", `${s.item_count} 条 · ${s.created_at.replace("T", " ")} · 所选运行方式：${s.config.runtime}`));
      if (s.validation.scope) content.appendChild(make("p", "处理范围：" + scopeText(s.validation.scope)));
      const counts = { 全文: 0, 摘要: 0, 仅标题: 0 }; s.sources.forEach(i => counts[i.material]++);
      content.appendChild(make("p", `材料边界：${counts.全文} 条全文、${counts.摘要} 条摘要、${counts.仅标题} 条仅标题。日期默认报道日期；推文/个人实测/单源材料未独立核实。全量输入不证明重要事件没有遗漏。`));
      s.body.split("\n").forEach(line => {
        if (!line.trim()) return;
        const h = line.match(/^(#{1,3})\s+(.+)/), node = make(h ? (h[1].length === 1 ? "h3" : "h4") : "p");
        inline(h ? h[2] : line.replace(/^[-*] /, ""), node, sources); content.appendChild(node);
      });
      content.appendChild(make("p", s.validation.limitation));
      const details = make("details"), summary = make("summary", `实际总结来源（${s.sources.length} 条，点击展开）`); details.appendChild(summary);
      s.sources.forEach(i => {
        const p = make("section"); p.dataset.summaryRef = i.ref; p.tabIndex = -1;
        p.append(make("h4", `${i.ref} · ${i.date || "报道日期不明"} · ${i.source_name || i.source}`), make("p", i.title));
        if (i.summary) p.appendChild(make("p", i.summary));
        try {
          const u = new URL(i.url);
          if (["https:", "http:"].includes(u.protocol) && !u.username && !u.password) {
            const a = make("a", "打开原新闻"); a.href = u.href; a.target = "_blank"; a.rel = "noopener noreferrer"; p.appendChild(a);
          }
        } catch (_) { /* no unsafe source link */ }
        details.appendChild(p);
      });
      content.appendChild(details); renderList(totalRecords);
    } catch (e) { if (current === generation) status.textContent = e.message; }
  }
  async function finishResult(id) {
    const current = generation, bound = token;
    if (!dialog.open) { dialog.showModal(); window.dispatchEvent(new Event("news-summary-visibility")); }
    window.dispatchEvent(new Event("news-summary-completed"));
    // Fetch history without observing the same terminal job again.
    const x = await loadHistory();
    if (current !== generation || bound !== token) { await observeListing(x); return; }
    if (active?.id !== id) return;
    await openDetail(id);
  }
  async function receiveJob(job, attach = false) {
    if (job && job.database_token !== token) return;
    if (job && active?.id === job.id && !running(active) && running(job)) return;
    const key = job ? `${token}:${job.id}` : "";
    if (job && (attach || running(job))) watched.add(key);
    showJob(job);
    if (running(job)) { schedule(); return; }
    clearTimeout(timer);
    if (job?.status === "completed" && watched.has(key) && !completed.has(key)) {
      // Claim the transition before any await; overlapping responses notify once.
      completed.add(key);
      await finishResult(job.id);
    }
  }
  async function loadHistory(append = false) {
    const current = generation, revision = bindingVersion, request = ++historyRequest;
    const valid = () => current === generation && revision === bindingVersion && request === historyRequest;
    let x;
    try { x = await api(`/api/news-summaries?offset=${append ? entries.length : 0}`); }
    catch (e) { if (!valid()) return null; throw e; }
    // A newer list, a creation intent, or a job transition supersedes this snapshot.
    if (!valid()) return null;
    if (token && token !== x.database_token) {
      generation++; selected = ""; entries = []; showJob(null); clearTimeout(timer);
      watched.clear(); completed.clear();
      content.replaceChildren(make("p", "已切换数据库，显示新数据库的历史。"));
    }
    token = x.database_token; entries = append ? entries.concat(x.items) : x.items;
    totalRecords = x.total; renderList(totalRecords);
    return { listing: x, generation, token, revision: bindingVersion, request };
  }
  async function observeListing(x) {
    // Recheck after await as well: a POST/poll may bind a job between continuations.
    if (!x || x.generation !== generation || x.token !== token || x.revision !== bindingVersion || x.request !== historyRequest) return;
    await receiveJob(x.listing.active || x.listing.latest_job);
  }
  async function reload(append = false) {
    await observeListing(await loadHistory(append));
  }
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!active || !running(active)) return;
      const jobId = active.id, current = generation, bound = token;
      try {
        const x = await api(`/api/news-summaries/jobs/${encodeURIComponent(jobId)}`);
        if (current !== generation || bound !== token || active?.id !== jobId) return;
        if (x.job.database_token !== token) { await reload(); return; }
        await receiveJob(x.job);
      } catch (e) { if (current !== generation || bound !== token) return; status.textContent = e.message; if (dialog.open) timer = setTimeout(() => reload().catch(e => { status.textContent = e.message; }), 3000); }
    }, 1200);
  }
  async function open() { if (!dialog.open) { dialog.showModal(); window.dispatchEvent(new Event("news-summary-visibility")); } try { await reload(); return true; } catch (e) { status.textContent = e.message; return false; } }
  function scopeText(scope) {
    if (!scope) return "";
    const x = scope.excluded_by || {};
    const counts = Number.isInteger(scope.feed_visible_unread_count)
      ? `新闻流可见未读 ${scope.feed_visible_unread_count} 条；总结锁定未读 ${scope.locked_count} 条，其中含已关闭信源 ${scope.hidden_source_unread_count || 0} 条。关闭信源仅在新闻流隐藏，仍参与总结候选及成功后标读；Bloomberg视频不在本次范围。\n`
      : "";
    return counts + `将总结 ${scope.summarized_count} 条；另有 ${scope.excluded_count} 条不进入总结，但成功后也将标为已读。清理范围共 ${scope.locked_count} 条。\n排除：日期 ${x.date || 0}、条数 ${x.count || 0}、输入大小 ${x.size || 0}。\n日期缺失/无效 ${scope.undated_count || 0} 条，其中纳入 ${scope.undated_summarized || 0} 条；不猜日期。`;
  }
  async function start() {
    if (busy) return;
    if (!await open() || busy || running(active)) return;
    const current = generation, bound = token, key = `news-summary-request-${token}`;
    busy = true; bindingVersion++; controls();
    status.textContent = "正在筛选未读并计算预览，尚未开始生成或标读。";
    let submitted = false, preview = null;
    try {
      let requestId = sessionStorage.getItem(key);
      if (!requestId) { requestId = requestUUID(); sessionStorage.setItem(key, requestId); }
      const prepared = await api("/api/news-summaries/prepare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId, database_token: bound }) });
      if (current !== generation || bound !== token) return;
      if (prepared.job) { sessionStorage.removeItem(key); await receiveJob(prepared.job, true); return; }
      preview = prepared.preview;
      if (!preview || preview.database_token !== bound) throw new Error("预览数据库不匹配，请重新预览");
      const scope = preview.scope, text = scopeText(scope);
      status.textContent = `预览 · ${preview.start_date} → ${preview.end_date}\n${text}`;
      const confirmed = window.confirm(`实际总结日期：${preview.start_date} → ${preview.end_date}\n${text}\n限制：${scope.limits.max_days} 个自然日、${scope.limits.max_items} 条，另按本次实际生成请求大小筛选。\n仅在总结通过基本检查并成功保存后，才将全部锁定积压标读；失败或取消不改，新到新闻不受影响。\n预览有效15分钟，使用本次固定快照。继续吗？`);
      if (current !== generation || bound !== token) return;
      if (!confirmed) {
        sessionStorage.removeItem(key);
        await api(`/api/news-summaries/previews/${encodeURIComponent(preview.id)}/discard`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ database_token: bound }) }).catch(() => {});
        if (current === generation && bound === token) status.textContent = "已取消启动，没有执行生成或改变未读状态。";
        return;
      }
      status.textContent = "正在启动新闻总结，提交已确认的固定快照；创建成功后将显示生成进度。";
      submitted = true;
      const x = await api("/api/news-summaries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId, database_token: bound, preview_id: preview.id }) });
      if (current !== generation || bound !== token) return;
      sessionStorage.removeItem(key); await receiveJob(x.job, true);
    } catch (e) {
      if (["summary_settings_changed", "summary_preview_invalid"].includes(e.code)) sessionStorage.removeItem(key);
      const message = String(e.message || e).replace(/[。.!！]+$/, "");
      if (current === generation && bound === token) status.textContent = submitted
        ? `启动请求失败：${message}。请刷新确认任务状态，未创建时可重试。`
        : `未能启动总结，尚未确认创建任务：${message}`;
    }
    finally { busy = false; controls(); }
  }
  $("startNewsSummary").addEventListener("click", () => start().catch(e => { status.textContent = e.message; }));
  $("summarizeUnreadBtn").addEventListener("click", () => start().catch(e => { status.textContent = e.message; }));
  ["navSummariesBtn", "topbarSummariesBtn"].forEach(id => $(id)?.addEventListener("click", open));
  dialog.addEventListener("close", () => window.dispatchEvent(new Event("news-summary-visibility")));
  $("closeNewsSummaries").addEventListener("click", () => dialog.close());
  $("refreshNewsSummaries").addEventListener("click", () => reload().catch(e => { status.textContent = e.message; }));
  $("moreNewsSummaries").addEventListener("click", () => reload(true).catch(e => { status.textContent = e.message; }));
  $("cancelNewsSummary").addEventListener("click", async () => {
    if (!running(active) || busy) return;
    const current = generation, bound = token, jobId = active.id;
    busy = true; controls();
    try { const x = await api(`/api/news-summaries/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ database_token: token }) }); if (current !== generation || bound !== token || active?.id !== jobId) return; if (x.job.database_token !== token) { await reload(); return; } await receiveJob(x.job); }
    catch (e) { if (current === generation && bound === token) status.textContent = e.message; }
    finally { busy = false; controls(); }
  });
})();
