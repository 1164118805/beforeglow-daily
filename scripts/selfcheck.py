#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每周体检：抓线上真实文件，检查可用性 / 数据完整 / 内容新鲜度，输出 insights.json。
只在发现问题时用 warn，其余都算 ok。跑不通不报错，照样写文件。
"""
import json
import os
import time
import urllib.request

SITE = os.environ.get("SITE_BASE", "https://beforeglow-2412.surge.sh")
OUT = "insights.json"
UA = {"User-Agent": "beforeglow-selfcheck/1.0"}

checks = []


def add(kind, title, detail):
    checks.append({"k": kind, "t": title, "d": detail})


def get(url, timeout=25):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {"ok": True, "code": r.status, "size": len(body), "ms": int((time.time() - t0) * 1000), "body": body}
    except Exception as e:
        return {"ok": False, "code": 0, "size": 0, "ms": int((time.time() - t0) * 1000), "err": repr(e)[:120]}


def jload(r):
    try:
        return json.loads(r["body"].decode("utf-8"))
    except Exception:
        return None


# ---------- 1. 可用性 ----------
targets = ["/", "/js/a5.js", "/topics.json", "/vocab.json", "/data.json", "/letters.json", "/hot_topics.json"]
bad, slow, total_ms = [], [], []
for t in targets:
    r = get(SITE + t)
    if r["ok"] and r["ms"] > 5500:
        # surge 新文件首次请求会走冷缓存，再取一次，用暖的那次
        r2 = get(SITE + t)
        if r2["ok"]:
            r = r2
    if not r["ok"] or r["code"] != 200:
        bad.append("%s(%s)" % (t, r.get("code") or r.get("err", "")[:24]))
    else:
        total_ms.append(r["ms"])
        if r["ms"] > 5500:
            slow.append("%s %dms" % (t, r["ms"]))
if bad:
    add("warn", "站点有资源打不开", "、".join(bad[:4]))
elif slow:
    add("warn", "站点有点慢", "、".join(slow[:3]))
else:
    add("ok", "站点可用", "%d 个入口全部 200，平均 %dms" % (len(targets), sum(total_ms) // max(1, len(total_ms))))

# ---------- 2. 数据完整 ----------
tp = jload(get(SITE + "/topics.json"))
if not tp or not isinstance(tp.get("list"), list):
    add("warn", "话题库读不到", "topics.json 结构异常")
else:
    lst = tp["list"]
    titles = [str(x[1]) for x in lst if isinstance(x, list) and len(x) > 1]
    short = [str(x[1]) for x in lst if isinstance(x, list) and len(x) < 6]
    dup = len(titles) - len(set(titles))
    if dup:
        add("warn", "话题有重复", "重复 %d 条，列表 %d 条" % (dup, len(lst)))
    elif short:
        add("warn", "话题字段不全", "%d 条不足 6 个字段，例如「%s」" % (len(short), short[0][:16]))
    else:
        add("ok", "话题库完整", "%d 条，字段齐全、无重复" % len(lst))

vo = jload(get(SITE + "/vocab.json"))
if vo and isinstance(vo.get("list"), list):
    v = vo["list"]
    vs = [str(x[1]) for x in v if isinstance(x, list) and len(x) > 1]
    if len(vs) < 30:
        add("warn", "词汇偏少", "只有 %d 条，建议补到 40+" % len(vs))
    else:
        add("ok", "词汇库正常", "%d 条" % len(vs))

dj = jload(get(SITE + "/data.json"))
if dj:
    jokes = len(dj.get("jokes") or [])
    drills = len(dj.get("drills") or [])
    says = sum(len(c.get("items") or []) for c in (dj.get("says") or []) if isinstance(c, dict))
    if jokes < 50 or drills < 10:
        add("warn", "本地内容偏少", "笑话 %d 条 / 练习 %d 条" % (jokes, drills))
    else:
        add("ok", "本地内容充足", "笑话 %d · 练习 %d · 话术 %d" % (jokes, drills, says))

# ---------- 3. 新鲜度 ----------
hot = jload(get(SITE + "/hot_topics.json"))
if hot:
    ts = int(hot.get("ts") or 0)
    age_h = (time.time() - ts) / 3600.0 if ts else 999
    ai_n = sum(1 for x in (hot.get("list") or []) if x.get("from") or x.get("mean"))
    if age_h > 48:
        add("warn", "热榜数据太旧", "%.0f 小时没更新（云端任务可能挂了）" % age_h)
    elif ai_n == 0:
        add("warn", "热榜没有 AI 内容", "只有标题，没出处/含义，检查 LLM_API_KEY")
    else:
        add("ok", "热榜是新的", "%.1f 小时前更新 · %d 条，其中 %d 条有 AI 说明" % (age_h, len(hot.get("list") or []), ai_n))

ai = None
try:
    ai = jload(get("https://cdn.jsdelivr.net/gh/1164118805/beforeglow-daily@main/topics_ai.json"))
except Exception:
    pass
if ai is not None:
    n = len(ai.get("map") or {})
    if n == 0:
        add("warn", "话题 AI 补全是空的", "topics_ai.json 里没有内容")
    else:
        add("ok", "话题 AI 补全", "%d 条" % n)

# ---------- 4. 体积 ----------
page = get(SITE + "/")
if page["ok"]:
    kb = page["size"] // 1024
    if kb > 220:
        add("warn", "首页偏大", "%dKB（超过 220KB 打开会慢）" % kb)
    else:
        add("ok", "首页体积正常", "%dKB" % kb)

warns = [c for c in checks if c["k"] == "warn"]
score = max(40, 100 - len(warns) * 9)
data = {
    "v": 1,
    "ts": int(time.time()),
    "at": time.strftime("%Y-%m-%d", time.localtime()),
    "score": score,
    "items": checks,
}
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("insights.json: score=%d, warn=%d" % (score, len(warns)))
for c in warns:
    print("  warn:", c["t"], "-", c["d"])
