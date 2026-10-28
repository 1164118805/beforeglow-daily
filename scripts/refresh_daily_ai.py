#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每天生成：小凉的信（letters_ai.json）+ 话术补包（says_ai.json）
用法：python3 scripts/refresh_daily_ai.py [--force]
没配 LLM key 时会自动退回免 key 的 DuckDuckGo；都不通就只打 warning，不写文件。
"""
import datetime
import json
import os
import re
import signal
import sys
import time
import urllib.request

SITE = os.environ.get("SITE_BASE", "https://beforeglow-2412.surge.sh")
LETTER_OUT = "letters_ai.json"
SAYS_OUT = "says_ai.json"
BASE = (os.environ.get("LLM_BASE_URL") or "").strip()
MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"
TOKEN = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")
CANDIDATES = []
if BASE:
    CANDIDATES.append((BASE, MODEL, "openai"))
CANDIDATES.append(("https://models.github.ai/inference/chat/completions", MODEL, "openai"))
CANDIDATES.append(("ddg", "gpt-4o-mini", "ddg"))

CATS = ["开场", "控场", "留人", "接梗", "要礼物", "下播", "自嘲", "夸人", "怼人", "冷场", "整活"]


class _HardTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise _HardTimeout("timeout")


def _with_timeout(fn, secs):
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


def _salvage(text):
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    for fn in (lambda: json.loads(t),
               lambda: json.loads(re.search(r"\[.*\]", t, re.S).group(0)),
               lambda: json.loads(re.search(r"\{.*\}", t, re.S).group(0))):
        try:
            v = fn()
            if isinstance(v, dict):
                return v.get("items") or v.get("list") or v
            return v
        except Exception:
            continue
    return None


def _ddg(sys_prompt, user_msg, timeout=60):
    ua = {"User-Agent": "Mozilla/5.0", "x-vqd-accept": "1"}
    req = urllib.request.Request("https://duckduckgo.com/duckchat/v1/status", headers=ua)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        vqd = r.headers.get("x-vqd-4") or ""
    if not vqd:
        raise RuntimeError("no vqd")
    body = {"model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": sys_prompt},
                         {"role": "user", "content": user_msg}]}
    req = urllib.request.Request(
        "https://duckduckgo.com/duckchat/v1/chat", data=json.dumps(body).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "x-vqd-4": vqd})
    buf = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            p = line[5:].strip()
            if p == "[DONE]":
                break
            try:
                d = json.loads(p)
            except Exception:
                continue
            if d.get("message"):
                buf.append(d["message"])
    return "".join(buf)


def chat(sys_prompt, user_msg, kind, url, model, timeout=55):
    if kind == "ddg":
        return _with_timeout(lambda: _ddg(sys_prompt, user_msg, timeout), timeout + 5)
    body = {"model": model,
            "messages": [{"role": "system", "content": sys_prompt},
                         {"role": "user", "content": user_msg}],
            "temperature": 0.9, "max_tokens": 1200}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
    d = json.loads(raw)
    return d["choices"][0]["message"]["content"]


def pick_provider():
    for url, model, kind in CANDIDATES:
        try:
            out = chat("只回复两个字：好的", "开始", kind, url, model, timeout=40)
            if out and len(out.strip()) > 0:
                print("AI ok:", url, model)
                return (url, model, kind)
        except Exception as e:
            print("probe fail:", url, model, repr(e)[:160])
    return None


LETTER_SYS = (
    "你叫小凉，是给抖音娱乐主播做疗愈站点的女生，语气温柔、克制、不鸡汤、不说教，"
    "像深夜里一个懂她的人在说话。写给一个正在硬撑的女主播。\n"
    "要求：1) 不要出现具体人名、公司、平台活动；2) 不要说「加油」「你最棒」这类空话；"
    "3) 300-420 字，3-4 段，每段之间用 \\n\\n；4) 结尾可以轻轻托她一句，但不要煽情。\n"
    "严格输出 JSON：{\"t\":\"标题（8字以内）\",\"b\":\"正文\"}，不要 markdown、不要代码块。"
)

SAYS_SYS = (
    "你是抖音娱乐主播的直播编导。写直播时能直接念出口的话术，口语、短、有画面，不要教程腔、不要解释。\n"
    "每条给一个「小标题」（4-7字，说明什么时候用）和一句「可以直接念的话」（20-45字，允许带引号里的原话）。\n"
    "输出 JSON 数组：[{\"n\":\"小标题\",\"x\":\"可以直接念的话\"}]，不要 markdown、不要代码块。"
)


def today_cn():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")


def main():
    force = "--force" in sys.argv
    prov = pick_provider()
    if not prov:
        print("::warning title=AI 不可用::今天不生成信和话术，站点继续用旧的")
        return

    url, model, kind = prov
    day = today_cn()
    changed = []

    # ---- 小凉的信 ----
    try:
        out = chat(LETTER_SYS, "今天是 " + day + "，写今天这一封。", kind, url, model, timeout=70)
        obj = _salvage(out) or {}
        if isinstance(obj, dict) and obj.get("t") and obj.get("b"):
            data = {"v": 1, "ts": int(time.time()), "date": day, "list": []}
            if os.path.exists(LETTER_OUT):
                try:
                    data = json.load(open(LETTER_OUT, encoding="utf-8"))
                except Exception:
                    pass
            lst = [x for x in data.get("list", []) if x.get("date") != day]
            lst.insert(0, {"date": day, "t": str(obj["t"]).strip(), "b": str(obj["b"]).strip()})
            data.update({"v": 1, "ts": int(time.time()), "date": day, "list": lst[:14]})
            json.dump(data, open(LETTER_OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            changed.append("letters")
            print("letter ok:", obj.get("t"))
        else:
            print("letter parse fail:", str(out)[:160])
    except Exception as e:
        print("letter fail", repr(e)[:160])

    # ---- 话术补包 ----
    data = {"v": 1, "ts": 0, "date": "", "map": {}}
    if os.path.exists(SAYS_OUT):
        try:
            data = json.load(open(SAYS_OUT, encoding="utf-8"))
        except Exception:
            pass
    m = data.get("map") or {}
    added = 0
    for cat in CATS:
        exist = [str(x[0]) for x in (m.get(cat) or []) if isinstance(x, list) and x]
        if not force and len(exist) >= 30:
            continue
        try:
            out = chat(SAYS_SYS, "分类：" + cat + "。已有效果不错的小标题：" + "、".join(exist[:12]) +
                       "。请给 2 条新的，不要和这些重复。", kind, url, model, timeout=55)
            arr = _salvage(out)
            if not isinstance(arr, list):
                continue
            for it in arr:
                if not isinstance(it, dict):
                    continue
                n = str(it.get("n") or "").strip()
                x = str(it.get("x") or "").strip()
                if not n or not x or n in exist:
                    continue
                m.setdefault(cat, []).append([n, x])
                exist.append(n)
                added += 1
        except Exception as e:
            print("says fail", cat, repr(e)[:120])
    if added:
        data.update({"v": 1, "ts": int(time.time()), "date": day, "map": m})
        json.dump(data, open(SAYS_OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        changed.append("says")
        print("says ok +", added)

    print("done:", changed)


if __name__ == "__main__":
    main()
