import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

# 1) 硬超时工具 + DuckDuckGo（免 key）provider
helper = '''

import signal


class _HardTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise _HardTimeout("request timed out")


def _with_timeout(fn, secs):
    """Linux 上用 SIGALRM 硬砍，避免请求挂住不出声。"""
    try:
        old = signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, secs)
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    except AttributeError:
        return fn()


def _ddg_chat(sys_prompt, user_msg, timeout=60):
    """DuckDuckGo AI Chat（免 key）：先拿 vqd，再走 SSE 流。"""
    ua = {"User-Agent": "Mozilla/5.0", "x-vqd-accept": "1"}
    req = urllib.request.Request("https://duckduckgo.com/duckchat/v1/status", headers=ua)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        vqd = r.headers.get("x-vqd-4") or ""
    if not vqd:
        raise RuntimeError("no vqd")
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ],
    }
    req = urllib.request.Request(
        "https://duckduckgo.com/duckchat/v1/chat",
        data=json.dumps(body).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "x-vqd-4": vqd},
    )
    out = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                d = json.loads(payload)
            except Exception:
                continue
            if d.get("message"):
                out.append(d["message"])
    return "".join(out)
'''

anchor = '\ndef http_json(url, timeout=40):'
assert s.count(anchor) == 1
s = s.replace(anchor, helper + anchor, 1)

# 2) ai_batch 支持 ddg 分支：给 ai_batch 加一个 kind 参数
s = s.replace('def ai_batch(chunk, old_map, timeout=60):', 'def ai_batch(chunk, old_map, timeout=60, kind="openai"):')
old_call = '''    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
        _ct = r.headers.get("content-type", "")'''
new_call = '''    if kind == "ddg":
        content = _with_timeout(lambda: _ddg_chat(SYS, json.dumps(payload, ensure_ascii=False), timeout), timeout + 5)
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        arr = json.loads(content)
        if isinstance(arr, dict):
            arr = arr.get("items") or arr.get("list") or []
        return _collect(arr)
    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
        _ct = r.headers.get("content-type", "")'''
assert s.count(old_call) == 1
s = s.replace(old_call, new_call)

# 3) 抽出结果收集逻辑 → _collect，openai 分支也用它
old_tail = '''    arr = json.loads(content)
    if isinstance(arr, dict):
        arr = arr.get("items") or arr.get("list") or []
    out = {}
    for it in arr:'''
new_tail = '''    arr = json.loads(content)
    if isinstance(arr, dict):
        arr = arr.get("items") or arr.get("list") or []
    return _collect(arr)


def _collect(arr):
    out = {}
    for it in arr:'''
assert s.count(old_tail) == 1
s = s.replace(old_tail, new_tail)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('ddg added')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
