from __future__ import annotations
import sqlite3, json, threading, time, uuid, subprocess, sys, os
from pathlib import Path
import pytest
import news_summaries as ns

NATIVE_CONFIG_STAMP = ns.native_config_stamp
from scanner import apply_schema


@pytest.fixture
def setup(tmp_path, monkeypatch):
    # Unit tests use deterministic metadata; real runtime metadata is exercised separately.
    monkeypatch.setattr(ns, "native_config_stamp", lambda config: [])
    p = tmp_path / "news.sqlite3"
    c = sqlite3.connect(p)
    apply_schema(c, Path(__file__).resolve().parents[1] / "schema.sql")

    def add(c, i, title=None, dt="2026-10-01"):
        c.execute(
            "INSERT INTO items(id,source_file,item_order,published_at,date,source,source_name,source_type,title,url,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                str(i),
                "synthetic.md",
                i,
                dt + " 10:00",
                dt,
                "test",
                "Synthetic",
                "site",
                title or f"公司报告订单增加{i}项",
                "https://example.test/" + str(i),
                dt,
                dt,
            ),
        )

    add(c, 1)
    add(c, 2, dt="2026-10-02")
    add(c, 3)
    c.execute(
        "INSERT INTO item_state(item_id,read_at,important_at,updated_at) VALUES(?,?,?,?)",
        ("3", "old-read", "old-important", "old"),
    )
    c.commit()
    c.close()
    state = {"path": p, "route": "route-a"}
    settings = {
        "agent": {
            "runtime": "codex",
            "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
        },
        "llm": {"pi_chat": {"provider": "test", "model": "test"}},
    }
    gate = threading.Event()
    gate.set()
    entered = threading.Event()
    calls = []

    def valid_body():
        return "## 本期变化\n\n2026-10-01，公司报告订单增加1项。[[N0001]]\n\n2026-10-02，公司报告订单增加2项。[[N0002]]"

    def audit():
        return {"body": valid_body()}

    def run(config, prompt, cancel, diag):
        calls.append((config, prompt))
        entered.set()
        while not gate.wait(0.01):
            if cancel():
                raise RuntimeError("summary_cancelled")
        if cancel():
            raise RuntimeError("summary_cancelled")
        return valid_body()

    service = ns.Service(
        lambda: state["path"], lambda: settings, lambda: state["route"], run
    )
    return p, state, service, gate, entered, calls, add, audit


def create(service):
    return service.create(str(uuid.uuid4()), service.listing()["database_token"])[0]


def wait(service, id):
    end = time.time() + 4
    while time.time() < end:
        j = service.job(id)
        if j["status"] not in ns.ACTIVE:
            return j
        time.sleep(0.01)
    raise AssertionError("worker timeout")


def reads(path):
    c = sqlite3.connect(path)
    try:
        return dict(c.execute("SELECT item_id,read_at FROM item_state"))
    finally:
        c.close()


def test_success_atomic_and_history(setup):
    p, state, s, gate, entered, calls, add, audit = setup
    j = create(s)
    r = wait(s, j["id"])
    assert r["status"] == "completed"
    d = s.detail(j["id"])
    assert d["item_count"] == 2 and len(d["sources"]) == 2
    assert d["validation"]["method"].startswith("basic")
    assert len(calls) == 1 and "1项" in calls[0][1] and "2项" in calls[0][1]
    assert reads(p)["1"] and reads(p)["2"] and reads(p)["3"] == "old-read"
    c = sqlite3.connect(p)
    assert (
        c.execute("SELECT important_at FROM item_state WHERE item_id='3'").fetchone()[0]
        == "old-important"
    )
    c.close()
    assert len(s.listing()["items"]) == 1


def test_new_news_manual_read_and_idempotency(setup):
    p, state, s, gate, entered, calls, add, audit = setup
    gate.clear()
    token = s.listing()["database_token"]
    key = str(uuid.uuid4())
    j, _ = s.create(key, token)
    assert entered.wait(2)
    same, created = s.create(key, token)
    assert same["id"] == j["id"] and not created
    same, created = s.create(str(uuid.uuid4()), token)
    assert same["id"] == j["id"] and not created
    c = sqlite3.connect(p)
    add(c, 4)
    c.execute(
        "INSERT INTO item_state(item_id,read_at,important_at,updated_at) VALUES('1','manual','keep','old')"
    )
    c.commit()
    c.close()
    gate.set()
    assert wait(s, j["id"])["status"] == "completed"
    assert "4" not in reads(p) and reads(p)["1"] == "manual"
    same, created = s.create(key, token)
    assert same["id"] == j["id"] and not created
    c = sqlite3.connect(p)
    assert (
        c.execute("SELECT important_at FROM item_state WHERE item_id='1'").fetchone()[0]
        == "keep"
    )
    c.close()


def test_cancel_during_execution(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    s.cancel(j["id"], j["database_token"])
    assert wait(s, j["id"])["status"] == "cancelled"
    assert "1" not in reads(p) and not s.listing()["items"]
    gate.set()


def test_failed_generation(setup):
    p, _, s, *_ = setup
    s.runner = lambda *a: (_ for _ in ()).throw(RuntimeError("summary_runtime_failed"))
    j = create(s)
    assert wait(s, j["id"])["status"] == "failed"
    assert "1" not in reads(p) and not s.listing()["items"]


@pytest.mark.parametrize("bad", ["empty", "whitespace", "not_string", "no_ref", "unknown", "malformed", "oversize"])
def test_basic_validation_fails_closed(setup, bad):
    p, _, s, _, _, _, _, make = setup
    body = make()["body"]
    cases = {
        "empty": "", "whitespace": "  \n ", "not_string": {"body": body},
        "no_ref": "没有引用", "unknown": body.replace("N0001", "N9999"),
        "malformed": body + " [[FAKE]]", "oversize": body + "文" * 800000,
    }
    count = []
    def runner(*a):
        count.append(1)
        return cases[bad]
    s.runner = runner
    j = create(s)
    result = wait(s, j["id"])
    assert result["status"] == "failed" and result["error"] == "summary_validation_failed"
    assert len(count) == 1 and "1" not in reads(p) and not s.listing()["items"]

@pytest.mark.parametrize("body", [
    "2026-10-01报道，公司订单有所变化。[[N0001]]",
    "公司近期订单有所变化，并无披露更多材料。[[N0001]]",
    "公司订单变化。[[N0001]]\n\n独立事件进展。[[N0002]]",
    "## 本期变化[[N0001]]\n\n同日，公司订单变化。[[N0001]]",
    "报道日期不明；材料只给出了标题。[[N0001]]",
])
def test_natural_body_no_audit_report_or_lexical_date_gate(setup, body):
    p, _, s, _, _, calls, _, _ = setup
    s.runner = lambda *a: body
    job = create(s)
    assert wait(s, job["id"])["status"] == "completed"
    assert s.detail(job["id"])["body"] == body
    assert "不保证" in s.detail(job["id"])["validation"]["limitation"]
    assert reads(p)["1"] and reads(p)["2"]


def test_database_switch(setup, tmp_path):
    p, state, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    other = tmp_path / "other.sqlite"
    c = sqlite3.connect(other)
    apply_schema(c, Path(__file__).resolve().parents[1] / "schema.sql")
    c.commit()
    c.close()
    state["path"] = other
    gate.set()
    end = time.time() + 2
    while s.workers and time.time() < end:
        time.sleep(0.01)
    assert not s.listing()["items"] and "1" not in reads(p) and reads(other) == {}
    c = sqlite3.connect(p)
    assert (
        c.execute("SELECT error FROM news_summary_jobs").fetchone()[0]
        == "summary_database_changed"
    )
    c.close()
    with pytest.raises(ValueError, match="summary_database_changed"):
        s.create(str(uuid.uuid4()), j["database_token"])


def test_saved_db_route_change(setup):
    p, state, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    state["route"] = "route-b"
    gate.set()
    end = time.time() + 2
    while s.workers and time.time() < end:
        time.sleep(0.01)
    assert "1" not in reads(p)
    with pytest.raises(ValueError, match="summary_database_changed"):
        s.listing()


def test_original_material_change(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    c = sqlite3.connect(p)
    c.execute("UPDATE items SET title='changed' WHERE id='1'")
    c.commit()
    c.close()
    gate.set()
    assert wait(s, j["id"])["error"] == "summary_source_changed" and "1" not in reads(p)


def test_save_failure_rolls_back_all(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    c = sqlite3.connect(p)
    c.execute(
        "CREATE TRIGGER reject_read BEFORE INSERT ON item_state WHEN NEW.item_id='2' BEGIN SELECT RAISE(ABORT,'blocked');END"
    )
    c.commit()
    c.close()
    gate.set()
    assert (
        wait(s, j["id"])["error"] == "summary_save_failed"
        and "1" not in reads(p)
        and not s.listing()["items"]
    )


def test_readback_failure_rolls_back(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    c = sqlite3.connect(p)
    c.execute(
        "CREATE TRIGGER corrupt_summary AFTER INSERT ON news_summaries BEGIN UPDATE news_summaries SET body='corrupted' WHERE id=NEW.id;END"
    )
    c.commit()
    c.close()
    gate.set()
    assert (
        wait(s, j["id"])["error"] == "summary_save_failed"
        and "1" not in reads(p)
        and not s.listing()["items"]
    )


def test_recovery_does_not_mark_read(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    s.cancel(j["id"], j["database_token"])
    wait(s, j["id"])
    c = sqlite3.connect(p)
    c.execute(
        "UPDATE news_summary_jobs SET status='checking',owner_pid=?", (os.getpid(),)
    )
    c.commit()
    c.close()
    result = s.listing()
    assert result["latest_job"]["error"] == "summary_interrupted" and "1" not in reads(
        p
    )
    gate.set()


def test_empty_and_bad_input(setup):
    p, _, s, *_ = setup
    token = s.listing()["database_token"]
    with pytest.raises(ValueError, match="invalid_request_id"):
        s.create([], token)
    with pytest.raises(ValueError, match="summary_database_changed"):
        s.create(str(uuid.uuid4()), "wrong")
    c = sqlite3.connect(p)
    c.execute(
        "INSERT INTO item_state(item_id,read_at,updated_at) VALUES('1','r','x'),('2','r','x')"
    )
    c.commit()
    c.close()
    with pytest.raises(ValueError, match="summary_empty"):
        create(s)


def test_corruption_after_read_insert_rolls_back(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    c = sqlite3.connect(p)
    c.execute(
        "CREATE TRIGGER corrupt_after_mark AFTER INSERT ON item_state BEGIN UPDATE news_summaries SET body='broken';END"
    )
    c.commit()
    c.close()
    gate.set()
    assert (
        wait(s, j["id"])["error"] == "summary_save_failed"
        and "1" not in reads(p)
        and not s.listing()["items"]
    )


def test_database_replacement_never_writes_new_file(setup, tmp_path):
    p, state, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    copy = tmp_path / "replacement.sqlite"
    source = sqlite3.connect(p)
    dest = sqlite3.connect(copy)
    source.backup(dest)
    dest.close()
    source.close()
    old = tmp_path / "old.sqlite"
    p.rename(old)
    copy.rename(p)
    gate.set()
    end = time.time() + 2
    while s.workers and time.time() < end:
        time.sleep(0.01)
    assert "1" not in reads(p) and "1" not in reads(old)
    view = s.listing()
    assert (
        not view["items"] and view["latest_job"]["error"] == "summary_database_changed"
    )


def test_runtime_config_is_snapshotted(setup):
    p, _, s, gate, entered, calls, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    values = s.settings_getter()
    values["agent"]["runtime"] = "pi"
    values["agent"]["codex"]["model"] = "changed"
    gate.set()
    assert wait(s, j["id"])["status"] == "completed"
    assert all(
        c[0]["runtime"] == "codex" and c[0]["codex"]["model"] == "test" for c in calls
    )


def test_native_config_metadata_change_stops(setup, monkeypatch):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    monkeypatch.setattr(ns, "native_config_stamp", lambda config: ["changed"])
    gate.set()
    assert wait(s, j["id"])["error"] == "summary_runtime_failed" and "1" not in reads(p)


def test_cancel_before_launch_registration(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    s.cancel(j["id"], j["database_token"])
    gate.set()
    assert wait(s, j["id"])["status"] == "cancelled" and "1" not in reads(p)


@pytest.mark.parametrize("during_transaction", [False, True])
def test_real_process_crash_recovery(setup, tmp_path, during_transaction):
    p, _, s, *_ = setup
    root = str(Path(__file__).resolve().parents[1])
    code = """
import sys,os,sqlite3,json,uuid
sys.path.insert(0,sys.argv[2]);import news_summaries as n
p=sys.argv[1];c=sqlite3.connect(p);c.row_factory=sqlite3.Row;c.executescript(n.SCHEMA)
s=n.snapshot(c);key=uuid.uuid4().hex
c.execute("INSERT OR IGNORE INTO news_summary_meta VALUES('database_uid','crashdb')")
token=n.sha([n.fingerprint(p),'crashdb'])
c.execute("INSERT INTO news_summary_jobs(id,request_id,database_token,status,owner_pid,snapshot_json,config_json,route_key,created_at,updated_at) VALUES(?,?,?,'checking',?,?,?,?,?,?)",(key,str(uuid.uuid4()),token,os.getpid(),n.js(s),'{}','route-a',n.now(),n.now()));c.commit()
if sys.argv[3]=='1':
 c.execute('BEGIN IMMEDIATE')
 c.execute("INSERT INTO news_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)",(key,'partial',s['start'],s['end'],2,n.now(),'partial',n.js(s['items']),'{}','{}','bad'))
 c.execute("INSERT INTO item_state(item_id,read_at,updated_at) VALUES('1','bad','bad')")
os._exit(19)
"""
    r = subprocess.run(
        [sys.executable, "-c", code, str(p), root, "1" if during_transaction else "0"]
    )
    assert r.returncode == 19
    x = s.listing()
    assert (
        x["latest_job"]["error"] == "summary_interrupted"
        and not x["items"]
        and "1" not in reads(p)
    )


def test_no_second_request_even_if_it_would_fail(setup):
    p, _, service, _, _, _, _, make = setup
    calls = []
    def run(*a):
        calls.append(1)
        if len(calls) > 1:
            raise RuntimeError("summary_runtime_failed")
        return make()["body"]
    service.runner = run
    job = create(service)
    assert wait(service, job["id"])["status"] == "completed"
    assert len(calls) == 1 and reads(p)["1"] and reads(p)["2"]

def test_first_prompt_contains_content_requirements(setup):
    p, _, service, _, _, calls, _, _ = setup
    job=create(service)
    assert wait(service,job["id"])["status"]=="completed"
    assert len(calls)==1
    prompt=calls[0][1]
    for requirement in ("日期", "数字", "同案", "事件", "因果", "来源", "不输出JSON"):
        assert requirement in prompt


def test_full_input_limit_before_model_call(setup):
    p, _, s, _, _, calls, _, _ = setup
    c = sqlite3.connect(p)
    c.execute("UPDATE items SET summary=?", ("文" * (800000),))
    c.commit()
    c.close()
    with pytest.raises(ValueError, match="summary_input_limit"):
        create(s)
    assert not calls and "1" not in reads(p)


def test_api_surface(setup, monkeypatch, tmp_path):
    p, _, s, gate, entered, _, _, _ = setup
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(p))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(tmp_path / "absent.json"))
    import app as module

    monkeypatch.setattr(module, "NEWS_SUMMARY_SERVICE", s)
    client = module.app.test_client()
    x = client.get("/api/news-summaries").get_json()
    token = x["database_token"]
    assert client.post("/api/news-summaries", json=[]).status_code == 400
    assert (
        client.post(
            "/api/news-summaries", json={"request_id": "bad", "database_token": token}
        ).status_code
        == 400
    )
    assert client.get("/api/news-summaries/jobs/missing").status_code == 404
    assert client.get("/api/news-summaries/missing").status_code == 404
    assert client.get("/api/news-summaries?offset=bad").status_code == 400
    key = str(uuid.uuid4())
    gate.clear()
    prepared = client.post("/api/news-summaries/prepare", json={"request_id":key,"database_token":token})
    assert prepared.status_code == 200
    preview_id = prepared.get_json()["preview"]["id"]
    response = client.post(
        "/api/news-summaries", json={"request_id": key, "database_token": token, "preview_id":preview_id}
    )
    assert response.status_code == 202
    j = response.get_json()["job"]
    assert entered.wait(2)
    dup = client.post(
        "/api/news-summaries", json={"request_id": key, "database_token": token, "preview_id":preview_id}
    )
    assert dup.get_json()["job"]["id"] == j["id"]
    cancelled = client.post(
        f'/api/news-summaries/jobs/{j["id"]}/cancel', json={"database_token": token}
    )
    assert cancelled.status_code == 200
    assert wait(s, j["id"])["status"] == "cancelled"
    assert (
        client.get(f'/api/news-summaries/jobs/{j["id"]}').get_json()["job"]["status"]
        == "cancelled"
    )
    assert "1" not in reads(p)
    gate.set()


@pytest.mark.parametrize("runtime", ["codex", "pi"])
def test_native_owned_child_success(setup, monkeypatch, tmp_path, runtime):
    p, _, _, _, _, _, _, make = setup
    fake = tmp_path / "fake.py"
    if runtime == "codex":
        events = [
            {
                "type": "thread.started",
                "thread_id": "11111111-1111-4111-8111-111111111111",
            },
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"id": "x", "type": "agent_message", "text": "完整答案"},
            },
            {"type": "turn.completed"},
        ]
    else:
        events = [{"type": "oar_result", "outcome": "completed", "answer": "完整答案"}]
    fake.write_text(
        "import sys,json\nsys.stdin.read()\nfor e in "
        + repr(events)
        + ":print(json.dumps(e),flush=True)"
    )
    command = lambda *a, **k: [sys.executable, str(fake)]
    monkeypatch.setattr(ns.codex_client, "require_ready", lambda: None)
    monkeypatch.setattr(ns.codex_client, "command", command)
    monkeypatch.setattr(ns, "bridge_command", command)
    diag = []
    answer = ns.run_native(
        {
            "runtime": runtime,
            "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
            "pi_provider": "test",
            "pi_model": "test",
        },
        "test",
        lambda: False,
        diag,
    )
    assert answer == "完整答案" and diag[0]["exit_code"] == 0 and diag[0]["terminal"]


@pytest.mark.parametrize(
    "mode",
    [
        "empty_answer",
        "stream_no_final",
        "bad_json",
        "nonzero",
        "startup",
        "post_terminal",
    ],
)
def test_native_failure_is_not_success(monkeypatch, tmp_path, mode):
    events = [
        {"type": "thread.started", "thread_id": "11111111-1111-4111-8111-111111111111"},
        {"type": "turn.started"},
    ]
    if mode == "empty_answer":
        events += [
            {
                "type": "item.completed",
                "item": {"id": "x", "type": "agent_message", "text": ""},
            },
            {"type": "turn.completed"},
        ]
    elif mode == "stream_no_final":
        events += [
            {
                "type": "item.updated",
                "item": {"id": "x", "type": "agent_message", "text": "流式片段"},
            }
        ]
    elif mode in ("nonzero", "post_terminal"):
        events += [
            {
                "type": "item.completed",
                "item": {"id": "x", "type": "agent_message", "text": "answer"},
            },
            {"type": "turn.completed"},
        ]
    code = "import sys,json\nsys.stdin.read()\n"
    if mode == "startup":
        code = 'import sys\nsys.stderr.write("Model provider custom not found API_KEY=secret")\nsys.exit(1)\n'
    elif mode == "bad_json":
        code += 'print("not-json")\n'
    else:
        code += "for e in " + repr(events) + ": print(json.dumps(e),flush=True)\n"
        if mode == "nonzero":
            code += "sys.exit(2)\n"
        if mode == "post_terminal":
            code += 'print(json.dumps({"type":"turn.completed"}),flush=True)\n'
    fake = tmp_path / "fake.py"
    fake.write_text(code)
    monkeypatch.setattr(ns.codex_client, "require_ready", lambda: None)
    monkeypatch.setattr(
        ns.codex_client, "command", lambda *a, **k: [sys.executable, str(fake)]
    )
    diag = []
    with pytest.raises(RuntimeError):
        ns.run_native(
            {
                "runtime": "codex",
                "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
            },
            "test",
            lambda: False,
            diag,
        )
    assert diag and not any("secret" in str(x) for x in diag)
    if mode == "startup":
        assert (
            diag[0]["exit_code"] == 1 and diag[0]["launch_hint"] == "provider_not_found"
        )


def test_native_cancel_reaps_owned_process(monkeypatch, tmp_path):
    fake = tmp_path / "fake.py"
    fake.write_text("import sys,time\nsys.stdin.read()\ntime.sleep(8)")
    monkeypatch.setattr(ns.codex_client, "require_ready", lambda: None)
    monkeypatch.setattr(
        ns.codex_client, "command", lambda *a, **k: [sys.executable, str(fake)]
    )
    start = time.monotonic()
    diag = []
    with pytest.raises(RuntimeError, match="summary_cancelled"):
        ns.run_native(
            {
                "runtime": "codex",
                "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
            },
            "test",
            lambda: time.monotonic() - start > 0.15,
            diag,
        )
    assert diag[0]["exit_code"] is not None and time.monotonic() - start < 4


def test_chinese_adjacent_dates_are_not_lexically_rejected(setup):
    p, _, service, _, _, _, _, make=setup
    c=service.connection(p)
    try: snap=ns.snapshot(c)
    finally:c.close()
    body=make()["body"].replace("2026-10-01，","2026-10-01报道，")
    assert ns.checked_body(body,snap)[0]==body


def test_pid_reuse_does_not_keep_task_running(setup):
    p, _, s, gate, entered, _, _, _ = setup
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    s.cancel(j["id"], j["database_token"])
    wait(s, j["id"])
    c = sqlite3.connect(p)
    c.execute(
        "UPDATE news_summary_jobs SET status='checking',owner_pid=?,owner_start='old unrelated process'",
        (os.getppid(),),
    )
    c.commit()
    c.close()
    assert s.listing()["latest_job"][
        "error"
    ] == "summary_interrupted" and "1" not in reads(p)
    gate.set()


@pytest.mark.parametrize("runtime", ["codex", "pi"])
def test_tool_events_stop_data_only_summary(monkeypatch, tmp_path, runtime):
    fake = tmp_path / "fake.py"
    if runtime == "codex":
        events = [
            {
                "type": "thread.started",
                "thread_id": "11111111-1111-4111-8111-111111111111",
            },
            {"type": "turn.started"},
            {
                "type": "item.started",
                "item": {
                    "id": "tool",
                    "type": "command_execution",
                    "command": "fake_tool",
                },
            },
        ]
    else:
        events = [{"type": "oar_tool", "tool": "fake_tool"}]
    fake.write_text(
        "import sys,json,time\nsys.stdin.read()\nfor e in "
        + repr(events)
        + ":print(json.dumps(e),flush=True)\ntime.sleep(8)"
    )
    monkeypatch.setattr(ns.codex_client, "require_ready", lambda: None)
    command = lambda *a, **kw: [sys.executable, str(fake)]
    monkeypatch.setattr(ns.codex_client, "command", command)
    monkeypatch.setattr(ns, "bridge_command", command)
    diagnostics = []
    with pytest.raises(RuntimeError, match="summary_tool_used"):
        ns.run_native(
            {
                "runtime": runtime,
                "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
                "pi_provider": "test",
                "pi_model": "test",
            },
            "test",
            lambda: False,
            diagnostics,
        )
    assert diagnostics[0]["exit_code"] is not None and not diagnostics[0]["terminal"]


def test_complete_final_line_without_newline(monkeypatch, tmp_path):
    events = [
        {"type": "thread.started", "thread_id": "11111111-1111-4111-8111-111111111111"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "x", "type": "agent_message", "text": "完整答案"},
        },
        {"type": "turn.completed"},
    ]
    fake = tmp_path / "fake.py"
    fake.write_text(
        'import sys,json\nsys.stdin.read()\nsys.stdout.write("\\n".join(json.dumps(e) for e in '
        + repr(events)
        + "))"
    )
    monkeypatch.setattr(ns.codex_client, "require_ready", lambda: None)
    monkeypatch.setattr(
        ns.codex_client, "command", lambda *a, **k: [sys.executable, str(fake)]
    )
    diag = []
    assert (
        ns.run_native(
            {
                "runtime": "codex",
                "codex": {"model": "test", "profile": "", "sandbox": "read-only"},
            },
            "test",
            lambda: False,
            diag,
        )
        == "完整答案"
    )


def test_summary_panel_blocks_underlying_auto_read():
    root = Path(__file__).resolve().parents[1]
    code = r"""
const fs=require('fs'),vm=require('vm');const text=fs.readFileSync('static/app.js','utf8');
const names=['summaryPanelObscuresFeed','scheduleFeedEndAutoReadIfNeeded','processFeedAutoReadByScroll','setupReadObserver'];
const blocks=names.map(n=>{const start=text.indexOf('function '+n+'(');const m=text.slice(start).match(/^[\s\S]*?\n}\n/);if(!m)throw Error(n);return m[0]});
const ctx={panel:{open:true},state:{collection:'feed',hasMore:false,total:4},clearCalls:0,marked:0,feedEndAutoReadTimer:null,feedEndAutoReadFiredKey:null,readObserver:null,enteredViewport:new Set(['1']),lastScrollDirectionDown:true,
 document:{hidden:false,getElementById(){return ctx.panel},querySelectorAll(){return []}},
 newsList:{getBoundingClientRect(){return {top:0,bottom:100}},querySelectorAll(){return [{dataset:{id:'1'},getBoundingClientRect(){return {top:-5,bottom:-1}}}]}},
 window:{setTimeout(fn){ctx.callback=fn;return 1}},
 clearFeedEndAutoReadTimer(){ctx.clearCalls++;ctx.feedEndAutoReadTimer=null},feedEndAutoReadKey(){return 'k'},isListHintVisible(){return true},rowIsRead(){return false},
 patchStateWithRollback(){ctx.marked++},
 IntersectionObserver:class{constructor(fn){ctx.observerCallback=fn}observe(){}disconnect(){}}
};vm.createContext(ctx);vm.runInContext(blocks.join('\n'),ctx);
ctx.scheduleFeedEndAutoReadIfNeeded();if(ctx.callback)throw Error('scheduled under modal');ctx.processFeedAutoReadByScroll();if(ctx.marked)throw Error('scroll marked under modal');
ctx.setupReadObserver();ctx.observerCallback([{target:{dataset:{id:'1'}},isIntersecting:false,boundingClientRect:{bottom:-1},rootBounds:{top:0}}]);if(ctx.marked)throw Error('observer marked under modal');
ctx.panel.open=false;ctx.processFeedAutoReadByScroll();if(ctx.marked!==1)throw Error('normal scroll regressed');
console.log('PASS overlay blocks feed-end/scroll/intersection read; normal scrolling retained');
"""
    result = subprocess.run(
        ["node", "-e", code], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_settings_save_serializes_with_summary_commit(setup, monkeypatch, tmp_path):
    p, state, s, gate, entered, _, _, _ = setup
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(p))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(tmp_path / "absent.json"))
    import app as module

    monkeypatch.setattr(module, "NEWS_SUMMARY_SERVICE", s)
    monkeypatch.setattr(
        module,
        "validate_runtime_settings",
        lambda body: {"database": {"path": "new-route"}},
    )

    def save(value):
        assert s.lock._is_owned()
        state["route"] = "route-b"

    monkeypatch.setattr(module, "save_app_settings", save)
    monkeypatch.setattr(module, "refresh_agent_session_expiries", lambda: None)
    monkeypatch.setattr(module, "serialize_runtime_settings", lambda: {})
    gate.clear()
    j = create(s)
    assert entered.wait(2)
    assert module.app.test_client().put("/api/settings", json={}).status_code == 200
    gate.set()
    end = time.time() + 2
    while s.workers and time.time() < end:
        time.sleep(0.01)
    assert "1" not in reads(p)


@pytest.mark.parametrize("kind", ["short", "missing"])
def test_natural_dates_do_not_require_a_second_report(setup,kind):
    p,_,service,_,_,_,_,make=setup
    c=service.connection(p)
    try:snap=ns.snapshot(c)
    finally:c.close()
    body=make()["body"].replace("2026-10-02，","10-02，" if kind=="short" else "")
    assert ns.checked_body(body,snap)[0]==body


@pytest.mark.parametrize(
    "mode",
    [
        "poll",
        "refresh",
        "cancel",
        "reopen",
        "closed-poll",
        "normal-cancel",
        "duplicate",
        "switch",
        "stale-poll",
        "stale-cancel",
        "stale-running",
        "old-history",
        "create-completed",
    ],
)
def test_bound_completion_full_frontend_controller(mode):
    # Run the complete production controller, not an extracted helper; mocked
    # DOM/HTTP/clock exercise races while no real news or model is involved.
    root = Path(__file__).resolve().parents[1]
    code = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/news_summaries.js','utf8');
function element(){return {handlers:{},open:false,disabled:false,textContent:'',classList:{toggle(){}},replaceChildren(){},appendChild(){},append(){},addEventListener(k,f){this.handlers[k]=f;},showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();}};}
const tick=()=>new Promise(r=>setImmediate(r));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
async function scenario(mode){
 const els={},requests=[],events=[];let state='checking',db='db-a',timer=null,hold=null;
 const pending={id:'owned-job',start_date:'2026-10-01',end_date:'2026-10-02',item_count:2};
 const job=()=>({...pending,status:state,database_token:db});
 const listing=()=>({ok:true,database_token:db,items:state==='completed'?[{...job(),created_at:'2026-10-13T13:00:00'}]:[],total:state==='completed'?1:0,active:['checking','generating'].includes(state)?job():null,latest_job:job()});
 const ctx={console,URL,Event:class{constructor(type){this.type=type;}},document:{getElementById(id){return els[id]??=element();},createElement:element,createTextNode:element},window:{dispatchEvent(e){events.push(e.type);},confirm(){return true;}},setTimeout(f){timer=f;return 1;},clearTimeout(){timer=null;},fetch:async(path,options={})=>{requests.push(path);let data;
 if(path.startsWith('/api/news-summaries?offset='))data=listing();
 else if(path.endsWith('/cancel')){state=mode==='normal-cancel'?'cancelled':'completed';data={ok:true,job:job()};}
 else if(path.includes('/jobs/'))data={ok:true,job:job()};
 else if(path==='/api/news-summaries/prepare')data={ok:true,preview:{id:'preview-1',database_token:'db-a',start_date:'2026-10-01',end_date:'2026-10-02',scope:{limits:{max_days:20,max_items:6000},summarized_count:2,excluded_count:0,locked_count:2,excluded_by:{}}}};
 else if(path==='/api/news-summaries'&&options.method==='POST'){state=mode==='create-completed'?'completed':'checking';data={ok:true,job:job()};}
 else data={ok:true,summary:{id:pending.id,database_token:db,title:'新闻总结',item_count:2,created_at:'2026-10-13T13:00:00',config:{runtime:'codex'},validation:{limitation:'限制'},sources:[],body:'内容'}};
 const saved=data;
 if(hold&&hold.match(path)){const h=hold;hold=null;h.entered.resolve();await h.release.promise;}
 return {ok:true,json:async()=>saved};},sessionStorage:{getItem(){},setItem(){},removeItem(){}},crypto:{randomUUID(){return 'x';}}};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const click=async(id)=>{await els[id].handlers.click();await tick();};
 const count=()=>events.filter(x=>x==='news-summary-completed').length;
 const detail=()=>requests.filter(p=>p==='/api/news-summaries/owned-job').length;
 if(mode==='old-history'){state='completed';await click('navSummariesBtn');assert.equal(count(),0);assert.equal(detail(),0);return;}
 if(mode==='create-completed'){state='cancelled';await click('summarizeUnreadBtn');assert.equal(count(),1);assert.equal(detail(),1);return;}
 await click('navSummariesBtn');assert(timer,'active polling scheduled');
 if(mode==='poll'){state='completed';await timer();}
 if(mode==='refresh'){state='completed';await click('refreshNewsSummaries');}
 if(mode==='reopen'){els.newsSummariesDialog.close();state='completed';await click('navSummariesBtn');}
 if(mode==='closed-poll'){els.newsSummariesDialog.close();state='completed';await timer();}
 if(mode==='cancel'||mode==='normal-cancel'){await click('cancelNewsSummary');}
 if(mode==='duplicate'){
   state='completed';const oldTimer=timer;
   await Promise.all([oldTimer(),click('refreshNewsSummaries')]);
   els.newsSummariesDialog.close();await click('refreshNewsSummaries');await click('moreNewsSummaries');
   assert(!els.newsSummariesDialog.open,'duplicate completion reopened closed panel');
 }
 if(mode==='switch'||mode==='stale-poll'||mode==='stale-cancel'||mode==='stale-running'){
   const h={match:p=>p.includes(mode==='stale-cancel'?'/cancel':'/jobs/'),entered:deferred(),release:deferred()};hold=h;
   if(mode!=='stale-running')state='completed';
   const request=mode==='stale-cancel'?els.cancelNewsSummary.handlers.click():timer();
   await h.entered.promise;
   if(mode==='stale-running'){state='completed';await click('refreshNewsSummaries');}
   else {db='db-b';state=mode==='switch'?'completed':'cancelled';await click('refreshNewsSummaries');}
   h.release.resolve();await request;await tick();
   if(mode==='stale-running'){assert(els.newsSummaryProgress.textContent.includes('总结已保存'),'stale pending regressed terminal state');}
 }
 await tick();
 const success=!['normal-cancel','switch','stale-poll','stale-cancel'].includes(mode);
 assert.equal(count(),success?1:0,`${mode}: completion event count`);
 assert.equal(detail(),success?1:0,`${mode}: result detail count`);
 if(success&&mode!=='duplicate')assert(els.newsSummariesDialog.open,'result panel should open');
 if(mode==='normal-cancel')assert(els.newsSummaryProgress.textContent.includes('已取消'));
}
(async()=>{const modes=process.argv[1]?[process.argv[1]]:['poll','refresh','cancel','reopen','closed-poll','normal-cancel','duplicate','switch','stale-poll','stale-cancel','stale-running','old-history','create-completed'];for(const m of modes){await scenario(m);console.log('PASS full controller '+m);}})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    r = subprocess.run(
        ["node", "-e", code, mode], cwd=root, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_cancel_after_commit_reports_completed(setup):
    p, _, s, _, _, _, _, _ = setup
    j = create(s)
    assert wait(s, j["id"])["status"] == "completed"
    before = reads(p)
    result = s.cancel(j["id"], j["database_token"])
    assert (
        result["status"] == "completed"
        and not result["cancel_requested"]
        and reads(p) == before
    )


def test_cancel_before_commit_wins(setup, monkeypatch):
    p, _, s, _, _, _, _, _ = setup
    ready = threading.Event()
    release = threading.Event()
    original = ns.checked_body

    def review(value, snapshot):
        result = original(value, snapshot)
        ready.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(ns, "checked_body", review)
    j = create(s)
    assert ready.wait(2)
    s.cancel(j["id"], j["database_token"])
    release.set()
    assert (
        wait(s, j["id"])["status"] == "cancelled"
        and "1" not in reads(p)
        and not s.listing()["items"]
    )


def test_native_config_fingerprint_is_metadata_only(tmp_path, monkeypatch):
    home = tmp_path / "native"
    project = tmp_path / "project"
    home.mkdir()
    (project / ".codex").mkdir(parents=True)
    global_config = home / "config.toml"
    project_config = project / ".codex/config.toml"
    global_config.write_text('model="fake"')
    project_config.write_text('model="fake2"')
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr(ns.codex_client, "ROOT", project)

    def forbidden(*a, **k):
        raise AssertionError("configuration content read")

    monkeypatch.setattr(Path, "read_text", forbidden)
    before = NATIVE_CONFIG_STAMP({"runtime": "codex"})
    global_config.write_bytes(b'model="fake3 with longer metadata"')
    after = NATIVE_CONFIG_STAMP({"runtime": "codex"})
    assert ns.sha(before) != ns.sha(after) and str(project_config) in str(after)


def test_double_click_rechecks_busy_after_async_open():
    root = Path(__file__).resolve().parents[1]
    code = r"""
const fs=require('fs'),vm=require('vm');const text=fs.readFileSync('static/news_summaries.js','utf8');const fn=text.match(/  async function start\(\) \{[\s\S]*?\n  }/)[0];
const ctx={busy:false,bindingVersion:0,requestUUID:()=>"fixed-id",active:null,generation:0,token:'db',open:async()=>{await Promise.resolve();return true},running:(j)=>j?.status==='pending',window:{confirm:()=>true},controls:()=>{},sessionStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},crypto:{randomUUID:()=> 'fixed-id'},scopeText:()=>'',api:async(path)=>{ctx.calls++;await Promise.resolve();return path.endsWith('/prepare')?{preview:{id:'p',database_token:'db',scope:{limits:{max_days:20,max_items:6000}}}}:{job:{id:'j',status:'pending'}}},calls:0,receiveJob:async(j)=>{ctx.active=j},schedule:()=>{},reload:async()=>{},status:{textContent:''}};
vm.createContext(ctx);vm.runInContext(fn,ctx);Promise.all([ctx.start(),ctx.start()]).then(()=>{if(ctx.calls!==2)throw Error('duplicate frontend request');console.log('PASS one preview and one create for rapid double click')});
"""
    r = subprocess.run(["node", "-e", code], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("phase", ["before-preflight", "during-post"])
@pytest.mark.parametrize("kind", ["history", "empty"])
@pytest.mark.parametrize("outcome", ["complete", "cancel"])
def test_stale_list_cannot_remove_new_task_binding(phase, kind, outcome):
    # A GET issued during POST has no newer GET to hide behind; this explicitly
    # verifies task-binding revision protection in addition to GET ordering.
    root = Path(__file__).resolve().parents[1]
    code = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/news_summaries.js','utf8');
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
function el(){const e={handlers:{},open:false,disabled:false,textContent:'',classes:{},classList:{toggle(k,v){e.classes[k]=v;}},replaceChildren(){},appendChild(){},append(){},addEventListener(k,f){this.handlers[k]=f;},showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();}};return e;}
const tick=()=>new Promise(r=>setImmediate(r));
async function scenario(phase,kind,outcome){
 const empty=kind==='empty',els={},events=[],requests=[];let serverNew=false,holdListing=false,timer=null;
 const postEntered=defer(),postRelease=defer(),listEntered=defer(),listRelease=defer();
 const old={id:'old-history',status:'completed',database_token:'db-a',start_date:'2026-10-01',end_date:'2026-10-01',item_count:1};
 const fresh={...old,id:'new-request',status:'checking',item_count:2};
 const listing=()=>({ok:true,database_token:'db-a',items:[...(!empty?[{...old,created_at:'2026-10-13T13:00:00'}]:[]),...(serverNew&&fresh.status==='completed'?[{...fresh,created_at:'2026-10-13T14:00:00'}]:[])],total:(empty?0:1)+(serverNew&&fresh.status==='completed'?1:0),active:serverNew&&fresh.status==='checking'?{...fresh}:null,latest_job:serverNew?{...fresh}:(empty?null:{...old})});
 const ctx={URL,console,Event:class{constructor(type){this.type=type;}},document:{getElementById(id){return els[id]??=el();},createElement:el,createTextNode:el},window:{confirm(){return true;},dispatchEvent(e){events.push(e.type);}},setTimeout(f){timer=f;return 1;},clearTimeout(){timer=null;},crypto:{randomUUID(){return 'request-key';}},sessionStorage:{getItem(){},setItem(){},removeItem(){}},fetch:async(path,o={})=>{
  requests.push(path);let data;
  if(path==='/api/news-summaries/prepare')data={ok:true,preview:{id:'preview-1',database_token:'db-a',start_date:'2026-10-01',end_date:'2026-10-02',scope:{limits:{max_days:20,max_items:6000},summarized_count:2,excluded_count:0,locked_count:2,excluded_by:{}}}};
  else if(path==='/api/news-summaries'&&o.method==='POST'){postEntered.resolve();await postRelease.promise;serverNew=true;data={ok:true,job:{...fresh}};}
  else if(path.startsWith('/api/news-summaries?')){
   data=listing();
   if(holdListing){holdListing=false;listEntered.resolve();await listRelease.promise;}
  }else if(path==='/api/news-summaries/jobs/new-request/cancel'){fresh.status='cancelled';data={ok:true,job:{...fresh}};}
  else if(path==='/api/news-summaries/jobs/new-request')data={ok:true,job:{...fresh}};
  else if(path==='/api/news-summaries/new-request')data={ok:true,summary:{...fresh,title:'新总结',created_at:'2026-10-13T14:00:00',config:{runtime:'codex'},validation:{limitation:'限制'},sources:[],body:'内容'}};
  else throw Error('Unexpected or wrong task '+path);
  return{ok:true,json:async()=>data};
 }};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const click=async(id)=>{await els[id].handlers.click();await tick();};
 await click('navSummariesBtn');
 let refresh,create;
 if(phase==='before-preflight'){
   holdListing=true;refresh=els.refreshNewsSummaries.handlers.click();await listEntered.promise;
   create=els.startNewsSummary.handlers.click();await postEntered.promise;
 }else{
   create=els.startNewsSummary.handlers.click();await postEntered.promise;
   // No newer GET follows this list: only a binding revision can invalidate it.
   holdListing=true;refresh=els.refreshNewsSummaries.handlers.click();await listEntered.promise;
 }
 postRelease.resolve();await create;await tick();
 const bound=()=>els.startNewsSummary.disabled&&!els.cancelNewsSummary.classes.hidden&&timer&&els.newsSummaryProgress.textContent.includes('正在自动核对');
 assert(bound(),'new job bound after create');
 listRelease.resolve();await refresh;await tick();
 assert(bound(),'late listing unbound new job or removed cancel/poll');
 if(outcome==='cancel'){
   await click('cancelNewsSummary');assert(requests.includes('/api/news-summaries/jobs/new-request/cancel'));
   assert(els.newsSummaryProgress.textContent.includes('已取消'));assert(!timer);
 }else{
   fresh.status='completed';await timer();await tick();
   assert(els.newsSummariesDialog.open,'new result not opened');
   assert.equal(requests.filter(p=>p==='/api/news-summaries/new-request').length,1);
 }
 await click('refreshNewsSummaries');await click('moreNewsSummaries');
 assert.equal(events.filter(x=>x==='news-summary-completed').length,outcome==='cancel'?0:1,'completion notification count');
 assert.equal(requests.filter(p=>p==='/api/news-summaries/new-request').length,outcome==='cancel'?0:1,'detail opened exactly once');
 console.log('PASS full controller stale list',phase,kind,outcome);
}
const [phase='before-preflight',kind='history',outcome='complete']=process.argv.slice(1);
scenario(phase,kind,outcome).catch(e=>{console.error(e);process.exitCode=1;});
"""
    r = subprocess.run(
        ["node", "-e", code, phase, kind, outcome],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize(
    "mode",
    [
        "secure-success",
        "http-success",
        "http-existing",
        "http-failure",
        "http-network-failure",
        "http-retry",
        "unsupported-random",
        "crypto-failure",
        "storage-failure",
        "lost-created",
    ],
)
def test_startup_uuid_compatibility_and_feedback_full_controller(mode):
    root = Path(__file__).resolve().parents[1]
    code = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/news_summaries.js','utf8');
const tick=()=>new Promise(r=>setImmediate(r));
function element(){const e={handlers:{},open:false,disabled:false,textContent:'',classes:{},classList:{toggle(k,v){e.classes[k]=v;}},replaceChildren(){},appendChild(){},append(){},addEventListener(k,f){this.handlers[k]=f;},showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();}};return e;}
async function scenario(mode){
 const els={},events=[],posts=[],values=new Map(),detailReads=[];let timer=null,serverJob=null,randomCalls=0,nativeCalls=0,created=0;
 const fields={id:mode==='http-existing'?'existing-job':'new-job',database_token:'db-a',start_date:'2026-10-01',end_date:'2026-10-02',item_count:2};
 const crypto={getRandomValues(bytes){randomCalls++;assert.equal(bytes.length,16);if(mode==='crypto-failure')throw Error('安全随机数失败');return bytes.fill(255);}};
 if(mode==='secure-success')crypto.randomUUID=()=>{nativeCalls++;return '11111111-1111-4111-8111-111111111111';};
 if(mode==='unsupported-random')delete crypto.getRandomValues;
 const ctx={console,URL,crypto,Event:class{constructor(type){this.type=type;}},document:{getElementById(id){return els[id]??=element();},createElement:element,createTextNode:element},window:{confirm(){return true;},dispatchEvent(e){events.push(e.type);}},sessionStorage:{getItem(k){if(mode==='storage-failure')throw Error('浏览器存储不可用');return values.get(k)||null;},setItem(k,v){values.set(k,v);},removeItem(k){values.delete(k);}},setTimeout(fn){timer=fn;return 1;},clearTimeout(){timer=null;},fetch:async(path,options={})=>{
  let data,ok=true;
  if(path.startsWith('/api/news-summaries?'))data={ok:true,database_token:'db-a',items:serverJob?.status==='completed'?[{...serverJob,created_at:'2026-10-13T14:00:00'}]:[],total:serverJob?.status==='completed'?1:0,active:serverJob?.status==='checking'?{...serverJob}:null,latest_job:serverJob?{...serverJob}:null};
  else if(path==='/api/news-summaries/prepare')data={ok:true,preview:{id:'preview-1',database_token:'db-a',start_date:'2026-10-01',end_date:'2026-10-02',scope:{limits:{max_days:20,max_items:6000},summarized_count:2,excluded_count:0,locked_count:2,excluded_by:{}}}};
 else if(path==='/api/news-summaries'&&options.method==='POST'){
   const payload=JSON.parse(options.body);posts.push(payload);
   assert(els.newsSummaryProgress.textContent.includes('正在启动'),'no immediate startup feedback at POST');
   assert(els.startNewsSummary.disabled&&els.summarizeUnreadBtn.disabled,'buttons not disabled before POST');
   assert.equal(payload.database_token,'db-a');
   assert(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(payload.request_id),'invalid v4 UUID');
   if(mode==='http-failure'||(mode==='http-retry'&&posts.length===1)){ok=false;data={ok:false,message:'合成创建失败。'};}
   else if(mode==='http-network-failure')throw Error('网络中断');
   else{
    serverJob={...fields,status:'checking'};
    if(mode!=='http-existing')created++;
    if(mode==='lost-created')throw Error('响应丢失');
    data={ok:true,job:{...serverJob},created:mode!=='http-existing'};
   }
  }else if(path.startsWith('/api/news-summaries/jobs/'))data={ok:true,job:{...serverJob}};
  else {detailReads.push(path);data={ok:true,summary:{...serverJob,title:'合成总结',created_at:'2026-10-13T14:00:00',body:'合成正文',sources:[],config:{runtime:'codex'},validation:{limitation:'限制'}}};}
  return {ok,json:async()=>data};
 }};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const click=async(id)=>{await els[id].handlers.click();await tick();};
 if(['unsupported-random','crypto-failure','storage-failure'].includes(mode)){
  await click('summarizeUnreadBtn');
  assert.equal(posts.length,0);assert.equal(created,0);
  assert(els.newsSummaryProgress.textContent.includes('尚未确认创建任务'));
  assert(!els.startNewsSummary.disabled&&!els.summarizeUnreadBtn.disabled);
  return;
 }
 if(['http-failure','http-network-failure','http-retry','lost-created'].includes(mode)){
  await click('summarizeUnreadBtn');
  assert.equal(posts.length,1);assert(els.newsSummaryProgress.textContent.includes('启动请求失败'));
  assert(!els.startNewsSummary.disabled&&!els.summarizeUnreadBtn.disabled);
  assert.equal(values.size,1,'unconfirmed request key must survive failure');
  if(mode==='http-failure'||mode==='http-network-failure'){assert.equal(created,0);return;}
  if(mode==='http-retry'){
    await click('summarizeUnreadBtn');assert.equal(posts.length,2);
    assert.equal(posts[0].request_id,posts[1].request_id,'retry discarded idempotency key');
  }else{
    await click('navSummariesBtn');await click('summarizeUnreadBtn');
    assert.equal(posts.length,1,'lost creation duplicated instead of reattaching active job');
  }
 }else{
  await Promise.all([click('summarizeUnreadBtn'),click('summarizeUnreadBtn')]);
  assert.equal(posts.length,1,'rapid clicks duplicated POST');
 }
 assert(els.newsSummaryProgress.textContent.includes('正在自动核对'));
 assert(els.startNewsSummary.disabled&&!els.cancelNewsSummary.classes.hidden&&timer);
 if(mode!=='lost-created')assert.equal(values.size,0,'acknowledged request key not cleared');
 assert.equal(created,mode==='http-existing'?0:1);
 if(mode==='secure-success'){assert.equal(nativeCalls,1);assert.equal(randomCalls,0);}
 else {assert.equal(nativeCalls,0);assert.equal(randomCalls,1);assert.equal(posts[0].request_id,'ffffffff-ffff-4fff-bfff-ffffffffffff');}
 serverJob.status='completed';await timer();await tick();
 assert.equal(events.filter(x=>x==='news-summary-completed').length,1);
 assert.equal(detailReads.length,1);
 assert(!els.startNewsSummary.disabled&&els.newsSummariesDialog.open);
 console.log('PASS startup full controller',mode);
}
scenario(process.argv[1]||'http-success').catch(e=>{console.error(e);process.exitCode=1;});
"""
    r = subprocess.run(
        ["node", "-e", code, mode], cwd=root, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_summary_http_uuid_cache_bust():
    root = Path(__file__).resolve().parents[1]
    assert (
        "news_summaries.js?build=news-summary-all-sources-v2"
        in (root / "static/index.html").read_text()
    )

# Range/preview integration on synthetic fixture only.
def preview(s):
    key=str(uuid.uuid4()); token=s.listing()["database_token"]
    x=s.prepare(key,token)["preview"]
    return key,token,x

def stored_preview(p,x):
    c=sqlite3.connect(p)
    try:return json.loads(c.execute("SELECT snapshot_json FROM news_summary_previews WHERE id=?",(x["id"],)).fetchone()[0])
    finally:c.close()

def selected_runner(s, material):
    calls=[]
    def run(config,prompt,cancel,diag):
        calls.append(prompt)
        if cancel():raise RuntimeError("summary_cancelled")
        i=material["items"][0];ref=i["ref"]
        body=(i["date"]+"报道" if i["date"] else "报道日期不明")+"，"+i["title"]+"。[["+ref+"]]"
        return body
    s.runner=run
    return calls

def test_preview_immutable_new_arrivals_and_all_locked_read(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    s.settings_getter()["news_summary"]={"max_days":1,"max_items":1}
    key,token,x=preview(s)
    material=stored_preview(p,x)
    assert x["scope"]["locked_count"]==2 and x["scope"]["summarized_count"]==1
    assert material["summary_ids"]==["2"] and material["all_ids"]==["1","2"]
    assert x["start_date"]==x["end_date"]=="2026-10-02"
    assert "excluded_ids" not in x["scope"] and not calls and "1" not in reads(p)
    c=sqlite3.connect(p); add(c,4,dt="2026-10-03");c.commit();c.close()
    assert s.prepare(key,token)["preview"]["id"]==x["id"]
    run_calls=selected_runner(s,material)
    j,_=s.create(key,token,x["id"])
    assert wait(s,j["id"])["status"]=="completed"
    assert len(run_calls)==1 and reads(p)["1"] and reads(p)["2"] and "4" not in reads(p)
    d=s.detail(j["id"])
    assert d["item_count"]==1 and len(d["sources"])==1
    assert d["validation"]["scope"]["locked_count"]==2 and d["start_date"]=="2026-10-02"

@pytest.mark.parametrize("change",["settings","expiry","discard","source","wrong-id","wrong-key","wrong-db"])
def test_preview_rejection_does_not_start_or_clear(setup,change):
    p,state,s,gate,entered,calls,add,audit=setup
    key,token,x=preview(s)
    if change=="settings":s.settings_getter()["news_summary"]={"max_items":1}
    if change=="discard":s.discard_preview(x["id"],token)
    if change in ("expiry","source"):
        c=sqlite3.connect(p)
        if change=="expiry":c.execute("UPDATE news_summary_previews SET expires_at=0")
        else:c.execute("UPDATE items SET title='changed' WHERE id='1'")
        c.commit();c.close()
    with pytest.raises(ValueError):
        s.create(str(uuid.uuid4()) if change=="wrong-key" else key,
                 "bad" if change=="wrong-db" else token,
                 "bad" if change=="wrong-id" else x["id"])
    assert not calls and "1" not in reads(p)
    assert s.listing()["total"]==0 and not s.listing()["active"]

def test_limits_change_after_confirm_keeps_fixed_job(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    gate.clear(); key,token,x=preview(s)
    j,_=s.create(key,token,x["id"]);assert entered.wait(2)
    s.settings_getter()["news_summary"]={"max_days":1,"max_items":1}
    gate.set()
    assert wait(s,j["id"])["status"]=="completed" and reads(p)["1"] and reads(p)["2"]
    assert s.detail(j["id"])["config"]["limits"]["max_items"]==6000

@pytest.mark.parametrize("failure",["model","save","source","overflow"])
def test_excluded_locked_rows_never_read_on_failure(setup,monkeypatch,failure):
    p,state,s,gate,entered,calls,add,audit=setup
    s.settings_getter()["news_summary"]={"max_items":1}
    key,token,x=preview(s); material=stored_preview(p,x)
    original=selected_runner(s,material)
    fn=s.runner
    def run(*args):
        if failure=="model":raise RuntimeError("summary_runtime_failed")
        if failure=="source" and not original:
            c=sqlite3.connect(p);c.execute("UPDATE items SET title='changed-excluded' WHERE id='1'");c.commit();c.close()
        return fn(*args)
    s.runner=run
    if failure=="save":
        c=sqlite3.connect(p)
        c.execute("CREATE TRIGGER fail_range_save BEFORE INSERT ON news_summaries BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        c.commit();c.close()
    if failure=="overflow":
        encoder=ns.encoded_input_size
        monkeypatch.setattr(ns,"encoded_input_size",lambda prompt,cfg:ns.MAX_INPUT_BYTES+1)
    j,_=s.create(key,token,x["id"])
    r=wait(s,j["id"])
    assert r["status"]=="failed" and "1" not in reads(p) and "2" not in reads(p)
    assert s.listing()["total"]==0
    if failure=="overflow":assert len(original)==0 and r["error"]=="summary_input_limit"

def test_missing_dates_service_success_without_guesses(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    c=sqlite3.connect(p);c.execute("UPDATE items SET date='invalid',published_at='' WHERE id IN ('1','2')");c.commit();c.close()
    key,token,x=preview(s)
    selected_runner(s,stored_preview(p,x))
    j,_=s.create(key,token,x["id"])
    assert wait(s,j["id"])["status"]=="completed"
    assert x["start_date"]=="日期不明" and "日期不明" in s.detail(j["id"])["body"]
    assert reads(p)["1"] and reads(p)["2"]

def test_size_excluded_whole_rows_success_only(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    c=sqlite3.connect(p);c.execute("UPDATE items SET summary=? WHERE id='1'",("文"*800000,));c.commit();c.close()
    key,token,x=preview(s); material=stored_preview(p,x)
    assert material["summary_ids"]==["2"] and material["scope"]["excluded_ids"]["size"]==["1"]
    assert len(material["all_items"][0]["summary"])==800000
    assert x["scope"]["excluded_by"]=={"date":0,"count":0,"size":1}
    run_calls=selected_runner(s,material)
    j,_=s.create(key,token,x["id"])
    assert wait(s,j["id"])["status"]=="completed" and len(run_calls)==1
    assert reads(p)["1"] and reads(p)["2"]

def test_cancel_with_excluded_rows_no_clear(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    s.settings_getter()["news_summary"]={"max_items":1}
    gate.clear();key,token,x=preview(s)
    j,_=s.create(key,token,x["id"]);assert entered.wait(2)
    s.cancel(j["id"],token)
    assert wait(s,j["id"])["status"]=="cancelled"
    assert "1" not in reads(p) and "2" not in reads(p) and s.listing()["total"]==0
    gate.set()

def test_preview_discard_no_model_or_read(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    key,token,x=preview(s);s.discard_preview(x["id"],token)
    c=sqlite3.connect(p)
    assert c.execute("SELECT count(*) FROM news_summary_previews").fetchone()[0]==0
    assert c.execute("SELECT count(*) FROM news_summary_jobs").fetchone()[0]==0
    c.close()
    assert not calls and "1" not in reads(p)

def test_preview_database_route_rebind_rejected(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    key,token,x=preview(s);state["route"]="route-b"
    with pytest.raises(ValueError,match="summary_database_changed"):s.create(key,token,x["id"])
    assert not calls and "1" not in reads(p)

def test_empty_unread_preview_no_creation(setup):
    p,state,s,gate,entered,calls,add,audit=setup
    c=sqlite3.connect(p)
    c.executemany("INSERT INTO item_state(item_id,read_at,updated_at) VALUES(?,'manual','old')",[("1",),("2",)])
    c.commit();c.close()
    with pytest.raises(ValueError,match="summary_empty"):preview(s)
    assert s.listing()["total"]==0 and not calls

@pytest.mark.parametrize("bad",[{"max_days":0},{"max_items":True},{"max_days":1.5},{"max_items":"10"},None,[]])
def test_limits_settings_api_rejects_invalid(setup,monkeypatch,tmp_path,bad):
    p,_,s,_,_,calls,_,_=setup
    monkeypatch.setenv("NEWS_READER_DB_PATH",str(p))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH",str(tmp_path/"runtime.json"))
    import app as module
    monkeypatch.setattr(module,"NEWS_SUMMARY_SERVICE",s)
    monkeypatch.setattr(module,"has_secret",lambda *a:False)
    monkeypatch.setattr(module,"refresh_agent_session_expiries",lambda:None)
    client=module.app.test_client()
    payload={"llm":client.get("/api/settings").get_json()["llm"],"news_summary":bad}
    response=client.put("/api/settings",json=payload)
    assert response.status_code==400 and response.get_json()["error"]=="invalid_summary_limits"
    assert not (tmp_path/"runtime.json").exists() and not calls

def test_limits_settings_api_persist_and_unrelated_save(setup,monkeypatch,tmp_path):
    p,_,s,_,_,_,_,_=setup
    monkeypatch.setenv("NEWS_READER_DB_PATH",str(p))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH",str(tmp_path/"runtime.json"))
    import app as module
    monkeypatch.setattr(module,"NEWS_SUMMARY_SERVICE",s)
    monkeypatch.setattr(module,"has_secret",lambda *a:False)
    monkeypatch.setattr(module,"refresh_agent_session_expiries",lambda:None)
    client=module.app.test_client()
    payload=client.get("/api/settings").get_json()
    assert payload["news_summary"]=={"max_days":20,"max_items":6000}
    payload={"llm":payload["llm"],"news_summary":{"max_days":3,"max_items":2}}
    assert client.put("/api/settings",json=payload).status_code==200
    assert client.get("/api/settings").get_json()["news_summary"]=={"max_days":3,"max_items":2}
    del payload["news_summary"]
    assert client.put("/api/settings",json=payload).status_code==200
    assert json.loads((tmp_path/"runtime.json").read_text())["news_summary"]=={"max_days":3,"max_items":2}

@pytest.mark.parametrize("mode",["decline","mismatch","expired","settings-changed","success"])
def test_frontend_preview_confirm_contract(mode):
    code=r"""
const vm=require('vm'),fs=require('fs'),assert=require('assert');
const elements={},requests=[],values=new Map(),prompts=[];
function el(){return {handlers:{},open:false,disabled:false,textContent:'',classList:{toggle(){}},replaceChildren(){},appendChild(){},append(){},addEventListener(k,f){this.handlers[k]=f},showModal(){this.open=true},close(){this.open=false}}}
const mode=process.argv[1];
const preview={id:'fixed-preview',database_token:mode==='mismatch'?'db-b':'db-a',start_date:'2026-10-12',end_date:'2026-10-13',scope:{limits:{max_days:20,max_items:6000},locked_count:6,summarized_count:2,excluded_count:4,excluded_by:{date:2,count:2,size:0},undated_count:1,undated_summarized:0}};
const ctx={URL,console,Event:class{},crypto:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'},document:{getElementById(id){return elements[id]??=el()},createElement:el,createTextNode:el},window:{confirm(t){prompts.push(t);return mode!=='decline'},dispatchEvent(){}},sessionStorage:{getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)},setTimeout:()=>1,clearTimeout(){},fetch:async(path,options={})=>{
 requests.push({path,payload:options.body?JSON.parse(options.body):null});let data={ok:true},ok=true;
 if(path.includes('?offset='))data={ok:true,database_token:'db-a',items:[],total:0,active:null,latest_job:null};
 else if(path.endsWith('/prepare'))data={ok:true,preview};
 else if(path==='/api/news-summaries'){assert.equal(JSON.parse(options.body).preview_id,'fixed-preview');if(mode==='expired'||mode==='settings-changed'){ok=false;data={ok:false,error:mode==='expired'?'summary_preview_invalid':'summary_settings_changed',message:'重新预览'};}else data={ok:true,job:{id:'job',database_token:'db-a',status:'checking',start_date:preview.start_date,end_date:preview.end_date,item_count:2,scope:preview.scope}};}
 else assert(path.endsWith('/discard'));
 return {ok,json:async()=>data};
}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/news_summaries.js','utf8'),ctx);
(async()=>{
 await elements.summarizeUnreadBtn.handlers.click();
 const creates=requests.filter(r=>r.path==='/api/news-summaries');
 if(mode==='decline'){assert.equal(creates.length,0);assert(requests.some(r=>r.path.endsWith('/discard')));assert.equal(values.size,0);assert(elements.newsSummaryProgress.textContent.includes('已取消启动'));}
 else if(mode==='mismatch'){assert.equal(creates.length,0);assert.equal(prompts.length,0);assert(elements.newsSummaryProgress.textContent.includes('数据库不匹配'));}
 else{assert.equal(creates.length,1);assert.equal(prompts.length,1);assert(prompts[0].includes('总结 2 条')&&prompts[0].includes('4 条不进入总结')&&prompts[0].includes('共 6 条'));assert(prompts[0].includes('2026-10-12 → 2026-10-13'));assert.equal(values.size,0);if(mode!=='success')assert(elements.newsSummaryProgress.textContent.includes('重新预览'));}
 assert(!elements.startNewsSummary.disabled || mode==='success');
 console.log('PASS preview contract',mode);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    r=subprocess.run(["node","-e",code,mode],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr

@pytest.mark.parametrize("runtime",["codex","pi"])
def test_entire_job_has_one_complete_owned_process(setup,monkeypatch,tmp_path,runtime):
    p,_,service,_,_,_,_,make=setup
    marker=tmp_path/"calls.txt"
    fake=tmp_path/"once.py"
    answer=make()["body"]
    if runtime=="codex":
        events=[
            {"type":"thread.started","thread_id":"11111111-1111-4111-8111-111111111111"},
            {"type":"turn.started"},
            {"type":"item.completed","item":{"id":"x","type":"agent_message","text":answer}},
            {"type":"turn.completed"},
        ]
    else:
        events=[{"type":"oar_result","outcome":"completed","answer":answer}]
    fake.write_text("import sys,json\nfrom pathlib import Path\nsys.stdin.read()\nwith Path("+repr(str(marker))+").open('a') as f:f.write('call\\n')\nfor event in "+repr(events)+":print(json.dumps(event),flush=True)")
    monkeypatch.setattr(ns.codex_client,"require_ready",lambda:None)
    monkeypatch.setattr(ns.codex_client,"command",lambda *a,**k:[sys.executable,str(fake)])
    monkeypatch.setattr(ns,"bridge_command",lambda *a,**k:[sys.executable,str(fake)])
    service.settings_getter()["agent"]["runtime"]=runtime
    service.runner=ns.run_native
    job=create(service)
    assert wait(service,job["id"])["status"]=="completed"
    assert marker.read_text().splitlines()==["call"]
    c=sqlite3.connect(p)
    diag=json.loads(c.execute("SELECT diagnostic_json FROM news_summary_jobs WHERE id=?",(job["id"],)).fetchone()[0]);c.close()
    assert len(diag)==1 and diag[0]["exit_code"]==0 and diag[0]["terminal"]
    assert reads(p)["1"] and reads(p)["2"]
    assert service.detail(job["id"])["validation"]["method"].startswith("basic")

def test_excluded_sources_cannot_be_cited_as_if_summarized(setup):
    p,_,service,_,_,_,_,_=setup
    service.settings_getter()["news_summary"]={"max_items":1}
    key,token,x=preview(service)
    material=stored_preview(p,x)
    assert material["summary_ids"]==["2"]
    service.runner=lambda *a:"被排除的新闻也声称进入正文。[[N0001]]"
    job,_=service.create(key,token,x["id"])
    assert wait(service,job["id"])["error"]=="summary_validation_failed"
    assert "1" not in reads(p) and "2" not in reads(p)

def test_legacy_success_validation_is_still_readable(setup):
    p,_,service,_,_,calls,_,_=setup
    job=create(service)
    assert wait(service,job["id"])["status"]=="completed"
    old={"method":"automatic-fact-review-and-reference-date-check-v1","checks":[],"limitation":"旧版核对仍不保证无误"}
    c=sqlite3.connect(p);c.execute("UPDATE news_summaries SET validation_json=? WHERE id=?",(json.dumps(old),job["id"]));c.commit();c.close()
    assert service.detail(job["id"])["validation"]==old
    assert len(calls)==1 and service.listing()["total"]==1

def test_rendering_is_text_only_for_untrusted_body():
    root=Path(__file__).resolve().parents[1]
    source=(root/"static/news_summaries.js").read_text()
    assert "innerHTML" not in source
    assert "document.createTextNode" in source and "textContent" in source
    assert "另按本次实际生成请求大小筛选" in source
    assert "仅在总结通过基本检查并成功保存后" in source

def test_single_call_has_no_audit_format_or_draft_reserve(setup):
    p,_,service,_,_,calls,_,_=setup
    key,token,x=preview(service)
    assert set(x["scope"]["input_budget"])=={"generation_bytes","transport_limit_bytes"}
    job,_=service.create(key,token,x["id"])
    assert wait(service,job["id"])["status"]=="completed"
    assert len(calls)==1 and "checks" not in calls[0][1] and "待核草稿" not in calls[0][1]
    assert not hasattr(ns,"audit_prompt") and not hasattr(ns,"audited")

@pytest.mark.parametrize("failure", [False, True])
def test_feed_scope_includes_hidden_source_and_protects_videos_and_arrivals(setup, monkeypatch, failure):
    import app
    p, state, s, gate, entered, calls, add, audit = setup
    settings = s.settings_getter()
    settings["feed"] = {"hidden_source_subkeys": ["x/fxtrader"]}
    settings["news_summary"] = {"max_days": 30, "max_items": 1}
    monkeypatch.setattr(app, "current_runtime_settings", lambda: settings)
    s.scope_getter = app.news_summary_feed_scope
    with sqlite3.connect(p) as c:
        for i in range(4, 35):
            add(c, i, dt="2026-10-02")
        for i in (31, 32, 33):
            c.execute("UPDATE items SET url=? WHERE id=?", (f"https://www.bloomberg.com/news/videos/2026-10-02/{i}", str(i)))
        c.execute("UPDATE items SET url='https://x.com/fxtrader/status/34',source_type='x',source='x',source_name='fxtrader',date='2026-10-03',published_at='2026-10-03 10:00' WHERE id='34'")
    with s.connection(p) as c:
        assert len(ns.select_items(c)) == 33
    # 1,2 and 4..30 visible; 3 was already read.
    key, token, x = preview(s)
    material = stored_preview(p, x)
    assert x["scope"]["locked_count"] == 30
    assert x["scope"]["summarized_count"] == 1
    assert x["scope"]["excluded_count"] == 29
    assert not set(material["all_ids"]) & {"31", "32", "33"}
    with s.connection(p) as c:
        where, args, counts = app.news_summary_feed_scope(c)
        count = c.execute("SELECT COUNT(DISTINCT items.id) FROM items LEFT JOIN item_state st ON st.item_id=items.id " + where, args).fetchone()[0]
    assert count == 30
    assert counts["feed_visible_unread_count"] == 29
    assert x["scope"]["feed_visible_unread_count"] == 29
    assert x["scope"]["hidden_source_unread_count"] == 1
    assert "34" in material["all_ids"]
    assert material["summary_ids"] == ["34"]
    with sqlite3.connect(p) as c:
        add(c, 35, dt="2026-10-03")
    selected_runner(s, material)
    if failure:
        def fail(*args):
            raise RuntimeError("summary_runtime_failed")
        s.runner = fail
    j, _ = s.create(key, token, x["id"])
    result = wait(s, j["id"])
    assert result["status"] == ("failed" if failure else "completed")
    current = reads(p)
    for i in material["all_ids"]:
        assert bool(current.get(i)) is (not failure)
    assert all(not current.get(str(i)) for i in (31, 32, 33, 35))


@pytest.mark.parametrize("action", ["prepare", "create"])
def test_old_visibility_preview_requires_repreview(setup, action):
    p, state, s, gate, entered, calls, add, audit = setup
    key, token, x = preview(s)
    material = stored_preview(p, x)
    material["visibility_scope"] = "feed-visible-v1"
    with sqlite3.connect(p) as c:
        c.execute("UPDATE news_summary_previews SET snapshot_json=? WHERE id=?", (json.dumps(material), x["id"]))
    with pytest.raises(ValueError, match="summary_preview_invalid"):
        if action == "prepare":
            s.prepare(key, token)
        else:
            s.create(key, token, x["id"])
    assert not calls and not reads(p).get("1")
    assert preview(s)[2]["scope"]["locked_count"] == 2


def test_scope_prompt_discloses_visible_and_hidden_counts():
    source = (Path(__file__).resolve().parents[1] / "static/news_summaries.js").read_text()
    start = source.index("  function scopeText(scope)")
    end = source.index("  async function start()", start)
    script = source[start:end] + """
const text = scopeText({feed_visible_unread_count:29, hidden_source_unread_count:1,
 locked_count:30, summarized_count:30, excluded_count:0});
if (!text.includes('新闻流可见未读 29 条') || !text.includes('总结锁定未读 30 条')
 || !text.includes('已关闭信源 1 条') || !text.includes('成功后标读')) throw Error(text);
if (scopeText({locked_count:33}).includes('新闻流可见未读')) throw Error('invented legacy count');
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

def test_public_diagnostic_whitelists_scalar_evidence_only():
    raw = [{"exit_code": 1, "seconds": 2.5, "terminal": True, "stderr_present": True,
            "stderr": "Authorization: secret", "body": "private news", "config": {"key":"secret"}}]
    assert ns.public_diagnostic(json.dumps(raw)) == {"exit_code":1,"seconds":2.5,"terminal":True,"stderr_present":True}
    assert ns.public_diagnostic('["private news"]') == {}
    assert ns.public_diagnostic('{bad') == {}
