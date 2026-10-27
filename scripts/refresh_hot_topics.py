#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refresh_hot_topics.py — 多平台热榜 → hot_topics.json（每天 06:30 由 GitHub Actions 跑）

- 抖音（xcvts）、B站（官方 ranking）稳定抓取；微博/知乎等可选源失败就跳过
- 抓到的平台用今天的；没抓到的平台保留上一版（保证多平台不全丢）
- 过滤政治/军事/灾难/官媒，只留娱乐生活类
- 连续在榜天数写入 d（用于「持续热」）
"""
import json, os, re, sys, datetime, urllib.request

SOURCES = [
    ("抖音", "https://api.xcvts.cn/api/hotlist/dy"),
    ("B站", "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"),
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
    r"辽宁舰|舰|菲律宾|军事|演训|编队|海警|战机|航母|国防|解放军|台海|边境|军演|部队|军区"
)


def fetch(url):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
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
        if t and len(t) <= 40 and not BAD.search(t):
            out.append(t)
    return out


def main():
    prev = {}
    prev_list = []
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            prev_list = old.get("list", [])
            for x in prev_list:
                prev[x.get("t", "")] = int(x.get("d", 1) or 1)
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
    # 没抓到的平台：保留上一版
    for x in prev_list:
        p = x.get("p")
        t = x.get("t")
        if t and p not in ok:
            best[t] = {"p": p, "t": t, "h": min(int(x.get("h", 0) or 0), 500000), "d": int(x.get("d", 1) or 1)}
    # 抓到的：用今天的
    for t, x in fetched.items():
        d = min(7, (prev.get(t, 0) + 1) if t in prev else 1)
        best[t] = {"p": x["p"], "t": t, "h": x["h"], "d": d}

    lst = list(best.values())
    lst.sort(key=lambda x: -x["h"])
    out = {"v": 1, "at": datetime.date.today().isoformat(), "note": "全网多平台热榜（每天 06:30 更新）", "list": lst[:60]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("saved", len(out["list"]), "from", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
