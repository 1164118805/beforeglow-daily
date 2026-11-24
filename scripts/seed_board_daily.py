# -*- coding: utf-8 -*-
"""每天往 D1 的 board 表插 10~20 条留言（云端共用，所有人看到同一批）。

用法：python3 scripts/seed_board_daily.py
需要：CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID（GitHub Actions 里配 secret）
"""
import os, sys, json, time, random, urllib.request, urllib.error

DB = "beforeglow-db"
# 2026-11-24 修复：改用 Cloudflare REST API，不再依赖 wrangler/npx
# （GitHub Actions 上 wrangler 要求 Node>=22.12，而 runner 是 Node 20，直接退出）
# 注意：GitHub Actions 未配置 variable 时会注入空字符串，os.environ.get 的默认值不会生效
DB_ID = os.environ.get("CLOUDFLARE_D1_ID", "").strip() or "b0aa15c5-338a-42f4-be50-5d344e66de95"
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
D1_API = "https://api.cloudflare.com/client/v4/accounts/%s/d1/database/%s/query" % (ACCOUNT, DB_ID)
TTL = 7 * 24 * 3600 * 1000
HERE = os.path.dirname(os.path.abspath(__file__))
_BIG = os.path.join(HERE, "board_pool_big.json")
_NM = os.path.join(HERE, "names_pool.json")
NAMES_999 = json.load(open(_NM, encoding="utf-8")) if os.path.exists(_NM) else []
_POOL = os.path.join(HERE, "board_pool.json")
if os.path.exists(_BIG):
    POOL = json.load(open(_BIG, encoding="utf-8"))
else:
    POOL = json.load(open(_POOL, encoding="utf-8"))


def esc(t):
    return str(t).replace("'", "''")


def _d1_request(sql):
    """单条 SQL 走 Cloudflare REST API。返回 result 数组。"""
    body = json.dumps({"sql": sql}).encode("utf-8")
    req = urllib.request.Request(
        D1_API, data=body,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8", "ignore"))
    if not d.get("success"):
        raise RuntimeError("D1 返回失败: " + str(d.get("errors"))[:300])
    return d.get("result") or []


def d1(sql):
    """执行一条或多条 SQL（按分号拆开逐条发），返回最后一条的 result。
    坑：wrangler --command 只跑第一条，多行 INSERT 会静默丢掉——REST 逐条发没有这个问题。"""
    if not TOKEN or not ACCOUNT:
        print("缺少 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID（GitHub Secrets 未配置）")
        sys.exit(1)
    last = []
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        try:
            last = _d1_request(stmt)
        except Exception as e:
            print("D1 执行失败:", str(e)[:200])
            sys.exit(1)
    return last


def ai_lines(n):
    """让大模型现写几条。没配 LLM 或失败就返回空，由池子兜底。"""
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()
    model = os.environ.get("LLM_MODEL", "doubao-seed-2-1-lite-260915").strip()
    if not key:
        return []
    prompt = (
        "写 %d 条深夜直播间观众/主播在匿名留言板上的留言。要求：\n"
        "1. 每条 20~60 字，口语，像手机打字，不要标点规整；\n"
        "2. 内容围绕：熬夜开播、下播后的空、被看见、自我怀疑、一点点暖；\n"
        "3. 不要励志、不要金句、不要 emoji、不要提到 AI 或平台名；\n"
        "4. 每条带一个昵称（2~6 字，网名感）、一个心情（从：累/撑着/睡不着/今天有点好/不知道/刚下播 里选一个）；\n"
        "5. 输出严格 JSON 数组，元素形如 {\"n\":\"昵称\",\"m\":\"心情\",\"t\":\"正文\"}，不要任何解释。"
    ) % n
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "thinking": {"type": "disabled"},
    }).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        txt = d["choices"][0]["message"]["content"].strip()
        a, b = txt.find("["), txt.rfind("]")
        arr = json.loads(txt[a:b + 1])
        out = []
        for x in arr:
            if not isinstance(x, dict): continue
            t = str(x.get("t") or "").strip()
            nn = str(x.get("n") or "").strip()
            if 12 <= len(t) <= 90 and nn:
                out.append({"n": nn, "m": str(x.get("m") or "撑着").strip(), "t": t})
        print("AI 写了 %d 条" % len(out))
        return out
    except Exception as e:
        print("AI 生成失败（用池子兜底）:", str(e)[:120])
        return []


def d1q(sql):
    """查询专用：REST API 返回 [{results:[...], success:...}]，取 results。"""
    try:
        r = _d1_request(sql)
        if isinstance(r, list) and r:
            return (r[0] or {}).get("results") or []
        return []
    except Exception as e:
        print("D1 查询失败:", str(e)[:150])
        return []


def main():
    now = int(time.time() * 1000)
    today = time.strftime("%Y%m%d")

    # 已经在库里的编号（避免 7 天内重复）
    used = set()
    try:
        rows = d1q("SELECT uid FROM board WHERE uid LIKE 'mock_%'")
        for r in rows:
            u = str(r.get("uid") or "")
            parts = u.split("_")
            if len(parts) >= 3 and parts[-1].isdigit():
                used.add(int(parts[-1]))
    except Exception as e:
        print("读已有 uid 失败（继续）:", e)

    idxs = list(range(len(POOL)))
    random.seed(today)
    random.shuffle(idxs)
    fresh = [i for i in idxs if i not in used] or idxs

    n = 10 + (int(today) % 11)

    # 先让 AI 写一半（池子会越用越旧，AI 写的是新的）
    aiN = max(0, min(n // 2, 6))
    aiItems = ai_lines(aiN) if aiN else []
    lines = []
    for k, r in enumerate(aiItems):
        created = now - (1 + (k * 3) % 18) * 3600000
        lines.append(
            "INSERT INTO board (uid,uname,nick,anon,av,mood,txt,likes,created,expires,hidden) "
            "VALUES ('mock_ai_%s_%d','','%s',0,%d,'%s','%s',%d,%d,%d,0);" % (
                today, k, esc(r["n"]), (k * 5) % 8, esc(r["m"]), esc(r["t"]),
                (k % 3), created, created + TTL))
    remain = n - len(lines)

    # 同一天不许出现同名（同一屏两个「不会唱歌的主播」一眼假）
    used_names, used_head = set(), set()
    picks = []
    for _i in fresh:
        _nm = (POOL[_i].get("n") or "").strip()
        _tx = (POOL[_i].get("t") or "").strip()
        _hd = _tx[:10]
        if _nm and _nm in used_names:
            continue
        if _hd and _hd in used_head:      # 同一句开头别出现两次
            continue
        if _nm: used_names.add(_nm)
        if _hd: used_head.add(_hd)
        picks.append(_i)
        if len(picks) >= remain:
            break
    if len(picks) < remain:                      # 不够就退回不做昵称过滤
        picks = fresh[:remain]

    for k, i in enumerate(picks):
        r = POOL[i]
        created = now - (1 + (k * 3) % 20) * 3600000
        # 点赞 1~99：和「今天来过人数」（真实访客 + 基数）同一量级
        likes = 1 + (i * 37 + k * 11) % 99
        lines.append(
            "INSERT INTO board (uid,uname,nick,anon,av,mood,txt,likes,created,expires,hidden) "
            "VALUES ('mock_%s_%d','','%s',0,%d,'%s','%s',%d,%d,%d,0);" % (
                today, i, esc(r["n"]), r["a"], esc(r["m"]),
                esc(r["t"]),
                likes, created, created + TTL))

    print("今天插 %d 条" % len(lines))
    d1("\n".join(lines))

    # ── 给今天新插的留言配「别人回的那几句」（写进 board_reply，不动正文）
    try:
        _rp = os.path.join(HERE, "reply_pool.json")
        if os.path.exists(_rp):
            rpool = json.load(open(_rp, encoding="utf-8"))
            # 按主题分组：回复只回应这条留言说的事，不跨主题（不然像串台）
            by_k = {}
            for it in rpool:
                by_k.setdefault(it.get("k") or "live", []).append(it)
            for lst in by_k.values():
                random.shuffle(lst)
            used_txt = set()

            rows = d1q("SELECT id, uid FROM board WHERE uid LIKE 'mock_%s%%';" % today)
            rl = []
            used_nick = set()

            def pick_nick():
                """从 999 个网名里抽一个当天没用过的（抽不到就加后缀兜底）"""
                if not NAMES_999:
                    return random.choice(["小满", "阿柚", "阿枝", "十一", "楼下的猫", "橘子"])
                for _ in range(40):
                    nm = random.choice(NAMES_999)
                    if nm not in used_nick:
                        used_nick.add(nm)
                        return nm
                nm = random.choice(NAMES_999) + str(random.randint(1, 99))
                used_nick.add(nm)
                return nm
            for row in rows:
                rid = row["id"]
                if random.random() > 0.72:
                    continue
                # 从 uid 里取回池子索引 → 拿到这条留言的主题
                try:
                    idx = int(str(row.get("uid") or "").split("_")[-1])
                    kind = (POOL[idx].get("k") or "live")
                except Exception:
                    kind = "live"
                cands = by_k.get(kind) or by_k.get("live") or []
                for c in range(1 + random.randrange(3)):
                    if not cands:
                        break
                    pick = None
                    for t in cands:
                        if t["t"] not in used_txt:
                            pick = t; break
                    if not pick:
                        break
                    used_txt.add(pick["t"])
                    rl.append(
                        "INSERT INTO board_reply (bid,uid,uname,nick,anon,av,txt,created) VALUES "
                        "(%d,0,'','%s',0,%d,'%s',%d);" % (
                            rid, esc(pick_nick()),
                            (rid * 3 + c) % 12, esc(pick["t"]), now - (1 + c) * 900000))
            if rl:
                d1("\n".join(rl))
                print("配了 %d 句回复" % len(rl))
    except Exception as e:
        print("配回复失败（不影响留言）:", str(e)[:100])

    print("done")


if __name__ == "__main__":
    main()
