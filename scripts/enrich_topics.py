#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把站点上的本地话题/词汇过一遍免费 AI（GitHub Models），生成 topics_ai.json。
站点前端会自动读取并合并：{v, ts, map:{标题:{mean,from,tone,scene,ex}}}

用法：
  python3 scripts/enrich_topics.py            # 增量（默认 30 天内不重复跑）
  python3 scripts/enrich_topics.py --force    # 强制全量重跑
"""
import json
import os
import re
import sys
import time
import urllib.request

SITE = os.environ.get("SITE_BASE", "https://beforeglow-2412.surge.sh")
OUT = "topics_ai.json"
AI_URL = os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference/chat/completions"
AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"
# 候选端点/模型（第一个探测成功的会被采用）
CANDIDATES = [
    ("https://models.github.ai/inference/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/v1/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/inference/v1/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/chat/completions", "openai/gpt-4o-mini"),
    ("https://api.github.ai/models/inference/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/inference", "openai/gpt-4o-mini"),
]
if os.environ.get("LLM_BASE_URL"):
    CANDIDATES.insert(0, (os.environ["LLM_BASE_URL"], AI_MODEL))
TOKEN = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")
BATCH = 10
DEADLINE = 9 * 60  # 全流程最多跑 9 分钟，超时就写已有的
MAX_AGE = 30 * 24 * 3600

SYS = (
    "你是中文直播编导，服务对象是抖音娱乐主播。给你一批条目标题（话题/词汇/热梗），"
    "给每一条写直播里能直接用的小卡片。全部说人话，不要教程腔，不要「作为一个AI」这类废话。\n"
    "字段：\n"
    "mean=含义（这是什么、现在大家怎么用它，20-40字，不要复述标题）\n"
    "from=出处（怎么来的：哪部剧/哪个视频/哪个平台/大概什么时候。已给「已知出处」就沿用并说清楚；"
    "真的查不到就写「没有单一可考的最初出处」，绝对不要编造剧名、人名、年份）\n"
    "tone=调性（2-6字，如「自嘲」「温和治愈」「轻松吐槽」）\n"
    "scene=场景（直播里什么时候用，列2-3个，用「、」隔开）\n"
    "ex=使用示范（2-3条对话，先「观众：…」换行再「你：…」）\n"
    "stale=时效判断：这条今天已经没人用了（特效失效、节日已过、事件结束超一个月）写 1，否则写 0；拿不准写 0\n"
    "fresh=大概什么时候开始流行，格式 2025-09，不确定留空\n"
    "严格输出 JSON 数组，每项 {t,mean,from,tone,scene,ex,stale,fresh}，t 必须和输入标题一字不差。"
    "不要 markdown、不要代码块、不要多余解释。"
)


def http_json(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "beforeglow-bot"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_pool():
    """从站点取本地话题与词汇，拼成待处理清单。"""
    items, seen = [], set()
    for name, url in (("topics.json", SITE + "/topics.json"), ("vocab.json", SITE + "/vocab.json")):
        try:
            d = http_json(url + "?e=" + str(int(time.time())))
            lst = d.get("list") if isinstance(d, dict) else d
            print("fetch", name, len(lst or []))
        except Exception as e:
            print("fetch fail", name, repr(e))
            continue
        for row in lst or []:
            if not isinstance(row, list) or len(row) < 2:
                continue
            t = str(row[1]).strip()
            if not t or t in seen:
                continue
            seen.add(t)
            items.append({
                "t": t,
                "k": str(row[0] or ""),
                "o": str(row[2] or ""),
                "r": str(row[3] or ""),
            })
    return items


def ai_batch(chunk, old_map, timeout=60):
    """chunk: [{t,k,o,r}] -> {t:{mean,from,tone,scene,ex}}"""
    payload = []
    for x in chunk:
        row = {"t": x["t"], "类型": x["k"], "开口": x["o"], "接话": x["r"]}
        prev = old_map.get(x["t"]) or {}
        if prev.get("from"):
            row["已知出处"] = prev["from"]
        if prev.get("mean"):
            row["已知含义"] = prev["mean"]
        payload.append(row)
    body = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.6,
        "max_tokens": 3500,
    }
    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
        _ct = r.headers.get("content-type", "")
    try:
        d = json.loads(raw)
    except Exception:
        print("RAW[%s][%s] %s" % (r.status, _ct, raw[:200].replace(chr(10), " ")))
        raise
    content = d["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    arr = json.loads(content)
    if isinstance(arr, dict):
        arr = arr.get("items") or arr.get("list") or []
    out = {}
    for it in arr:
        t = str(it.get("t") or "").strip()
        if not t:
            continue
        rec = {}
        for k in ("mean", "from", "tone", "scene", "ex", "fresh"):
            v = it.get(k)
            if isinstance(v, str) and v.strip():
                v = re.sub(r"^(含义|出处|调性|场景|使用示范|是什么)[：:]\s*", "", v.strip())
                rec[k] = v
        if str(it.get("stale")).strip() in ("1", "True", "true"):
            rec["stale"] = 1
        if rec:
            key = re.sub(r"[「」『』]", "", t)
            out[key or t] = rec
    return out


def main():
    force = "--force" in sys.argv
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}
    old_map = old.get("map") or {}
    age = int(time.time()) - int(old.get("ts") or 0)
    if not force and old_map and age < MAX_AGE:
        print("skip: topics_ai.json 还新（%.1f 天前），要重跑加 --force" % (age / 86400.0))
        return

    if not TOKEN:
        print("no token, abort")
        sys.exit(1)

    global AI_URL, AI_MODEL
    picked = None
    for url, model in CANDIDATES:
        try:
            AI_URL, AI_MODEL = url, model
            got = ai_batch([{"t": "测试", "k": "词汇", "o": "你好", "r": "你好呀"}], {}, timeout=40)
            if got:
                picked = (url, model)
                print("AI ok:", url, model)
                break
        except Exception as e:
            print("AI probe fail:", url, model, repr(e)[:200])
    if not picked:
        print("::error title=AI 不可用::所有候选端点都失败，看上面的 RAW 行")
        sys.exit(1)

    items = load_pool()
    print("total titles:", len(items))
    if not items:
        print("nothing to do")
        return

    done, fail = 0, 0
    t0 = time.time()
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        if time.time() - t0 > DEADLINE:
            print("deadline reached, keep what we have")
            break
        for attempt in range(2):
            try:
                got = ai_batch(chunk, old_map)
                for t, rec in got.items():
                    old_map[t] = rec
                done += len(got)
                print("batch %d-%d ok %d" % (i, i + len(chunk) - 1, len(got)))
                break
            except Exception as e:
                print("batch %d retry %d %r" % (i, attempt + 1, e))
                time.sleep(2)
        else:
            fail += len(chunk)
        time.sleep(1.5)

    if not old_map:
        print("::error title=AI 全失败::一条都没生成，先不写文件")
        sys.exit(1)
    out = {"v": 1, "ts": int(time.time()), "n": len(old_map), "map": old_map}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote %s  map=%d  ok=%d fail=%d" % (OUT, len(old_map), done, fail))


if __name__ == "__main__":
    main()
