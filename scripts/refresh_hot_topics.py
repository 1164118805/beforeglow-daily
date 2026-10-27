#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refresh_hot_topics.py — 多平台热榜 → hot_topics.json（每天 06:30 由 GitHub Actions 跑）

- 抖音（xcvts）、B站（官方 ranking）、微博/知乎（Tophub）稳定抓取
- 抓到的平台用今天的；没抓到的平台保留上一版（保证多平台不全丢）
- 过滤政治/军事/灾难/官媒，只留娱乐生活类
- 连续在榜天数写入 d（用于「持续热」）
"""
import json, os, re, sys, time, datetime, html, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

SOURCES = [
    ("抖音", "https://api.xcvts.cn/api/hotlist/dy"),
    ("B站", "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"),
    ("微博", "tophub:KqndgxeLl9"),
    ("知乎", "tophub:mproPpoq6O"),
    ("小红书", "rebang:xiaohongshu"),
    ("抖音", "https://api.vvhan.com/api/hotlist/douyinHot"),
    ("微博", "https://api.vvhan.com/api/hotlist/wbHot"),
    ("知乎", "https://api.vvhan.com/api/hotlist/zhihuHot"),
    ("B站", "https://api.vvhan.com/api/hotlist/bili"),
    ("抖音", "https://tenapi.cn/v2/douyinhot"),
    ("知乎", "https://tenapi.cn/v2/zhihuhot"),
]
OUT = os.path.join(os.getcwd(), "hot_topics.json")

BAD = re.compile(
    r"外交部|总统|主席|总书记|国务院|政府|两会|人大|政协|军委|军方|战争|导弹|台独|台湾|香港|澳门|西藏|新疆|"
    r"南海|访华|外交|领导|公安|警察|法院|判刑|被捕|起诉|事故|遇难|死亡|坠机|爆炸|火灾|地震|洪水|台风|"
    r"疫情|病毒|疫苗|股市|楼市|房价|政策|选举|特朗普|拜登|普京|习近平|泽连斯基|以色列|巴勒斯坦|乌克兰|"
    r"俄罗斯|美国|日本|韩国|朝鲜|伊朗|关税|制裁|央视|新闻联播|新华社|人民日报|祖国|丰收|阅兵|庆典|姆巴佩|"
    r"辽宁舰|舰|菲律宾|军事|演训|编队|海警|战机|航母|国防|解放军|台海|边境|军演|部队|军区|"
    "严正交涉|首富|身家|高质量发展|成绩单|论坛|峰会|开幕|闭幕|召开|考察|调研|签约|协议|贸易|经济|金融|银行|贷款|利率|汇率|GDP|增长|出口|进口|表彰|颁奖|冠军|夺冠|长征|革命|党史|抗战|解放战争|毒株|腹痛|确诊|病例|医院|医保|药|症状|发烧|咳嗽|流感|感染|病房|抢救|化疗|癌"
)


def fetch(url):
    if url.startswith("rebang:"):
        key = url.split(":", 1)[1]
        req = urllib.request.Request("https://rebang.today/?tab=" + key, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        items = []
        for m in re.finditer(r'href="(https?://www\.xiaohongshu\.com/[^"]+)"[^>]*>(.*?)</a>', raw, re.S):
            t = re.sub(r"<[^>]+>", "", m.group(2))
            t = html.unescape(t).replace("\n", " ").strip()
            if t:
                items.append({"title": t})
        return {"data": items}
    if url.startswith("tophub:"):
        node = url.split(":", 1)[1]
        req = urllib.request.Request("https://tophub.today/n/" + node, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        items = []
        for m in re.finditer(r'itemid="\d+">(.*?)</a>', raw, re.S):
            t = re.sub(r"<[^>]+>", "", m.group(1))
            t = html.unescape(t).replace("\n", " ").strip()
            if t:
                items.append({"title": t})
        return {"data": items}

    h = {"User-Agent": UA}
    if "bilibili" in url:
        h["Referer"] = "https://www.bilibili.com/"
        h["Accept"] = "application/json, text/plain, */*"
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def titles(d):
    if not d:
        return []
    arr = d.get("data") or d.get("result") or d.get("list") or (d if isinstance(d, list) else [])
    if isinstance(arr, dict):
        arr = arr.get("list") or arr.get("data") or []
    out = []
    for x in arr:
        if isinstance(x, str):
            t = x
        elif isinstance(x, dict):
            t = x.get("title") or x.get("name") or x.get("word") or x.get("hotword") or x.get("content") or ""
        else:
            continue
        t = re.sub(r"^#+|#+$", "", str(t)).replace("\n", " ").strip()
        if t and len(t) <= 40 and len(re.findall(r"[\u4e00-\u9fa5]", t)) >= 3 and not BAD.search(t):
            out.append(t)
    return out


AI_URL = "https://models.github.ai/inference/chat/completions"
AI_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")
AI_SYS = (
    "你是抖音娱乐主播的直播编导。给每个热榜话题写直播时能直接念的口语。"
    "不要解释概念，不要教程腔，不要套话。"
    "o=开口（1句，能直接说）；r=接话（1句）；e=延伸（1句）；a=避坑（1句）。"
    "od/rd/ed/ad=详细版，各2-3句，带具体背景、为什么、例子，必须有信息量。"
    "政治/军事/灾难/官媒话题跳过。"
    "严格输出 JSON 数组，每项 {t,o,r,e,a,od,rd,ed,ad}，不要 markdown、不要代码块。"
)


def _ai_chat(token, titles):
    body = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYS},
            {"role": "user", "content": "话题：" + json.dumps(titles, ensure_ascii=False)},
        ],
        "temperature": 0.8,
        "max_tokens": 4000,
    }
    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"]


def ai_enrich(lst):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("LLM_API_KEY")
    if not token:
        print("AI: no token, keep templates")
        return lst
    by = {x["t"]: x for x in lst}
    for i in range(0, len(lst), 10):
        chunk = lst[i:i + 10]
        titles = [x["t"] for x in chunk]
        try:
            content = _ai_chat(token, titles)
            content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
            arr = json.loads(content)
            if isinstance(arr, dict):
                arr = arr.get("items") or arr.get("list") or []
        except Exception as e:
            print("AI batch fail", i, repr(e))
            continue
        n = 0
        for item in arr:
            t = item.get("t")
            x = by.get(t)
            if not x:
                continue
            for k in ("o", "r", "e", "a", "od", "rd", "ed", "ad"):
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    x[k] = v.strip()
            n += 1
        print("AI batch", i, "ok", n)
    return lst


def main():
    prev = {}
    prev_list = []
    prev_fields = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            prev_list = old.get("list", [])
            for x in prev_list:
                prev[x.get("t", "")] = int(x.get("d", 1) or 1)
                f = {k: x[k] for k in ("o", "r", "e", "a", "od", "rd", "ed", "ad") if x.get(k)}
                if f:
                    prev_fields[x.get("t", "")] = f
        except Exception as e:
            print("prev read fail", e)

    fetched = {}
    counts = {}
    for pi, (p, url) in enumerate(SOURCES):
        try:
            ts = titles(fetch(url))
        except Exception as e:
            print("FAIL", p, url, repr(e))
            continue
        counts[p] = counts.get(p, 0) + len(ts)
        for rank, t in enumerate(ts[:20]):
            h = 1000000 - rank * 10000 - pi * 500
            if t not in fetched or h > fetched[t]["h"]:
                fetched[t] = {"p": p, "t": t, "h": h}

    if not fetched:
        print("no data; keep existing file")
        return 0

    ok = {p for p, c in counts.items() if c > 0}
    best = {}
    for x in prev_list:
        p = x.get("p")
        t = x.get("t")
        if t and p not in ok:
            best[t] = {"p": p, "t": t, "h": min(int(x.get("h", 0) or 0), 500000), "d": int(x.get("d", 1) or 1)}
            best[t].update(prev_fields.get(t, {}))
    for t, x in fetched.items():
        d = min(7, (prev.get(t, 0) + 1) if t in prev else 1)
        best[t] = {"p": x["p"], "t": t, "h": x["h"], "d": d}
        if t in prev_fields:
            best[t].update(prev_fields[t])

    lst = list(best.values())
    lst.sort(key=lambda x: -x["h"])
    try:
        lst = ai_enrich(lst)
    except Exception as e:
        print("AI enrich fail", repr(e))
    out = {"v": 1, "at": datetime.date.today().isoformat(), "ts": int(time.time()), "note": "全网多平台热榜（每天 06:30 更新，AI 整理）", "list": lst[:80]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("saved", len(out["list"]), "from", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
