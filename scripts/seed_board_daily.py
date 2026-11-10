# -*- coding: utf-8 -*-
"""每天往 D1 的 board 表插 10~20 条留言（云端共用，所有人看到同一批）。

用法：python3 scripts/seed_board_daily.py
需要：CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID（GitHub Actions 里配 secret）
"""
import os, sys, json, time, random, subprocess, urllib.request

DB = "beforeglow-db"
TTL = 7 * 24 * 3600 * 1000
HERE = os.path.dirname(os.path.abspath(__file__))
POOL = json.load(open(os.path.join(HERE, "board_pool.json"), encoding="utf-8"))


def esc(t):
    return str(t).replace("'", "''")


def d1(sql):
    """用临时 .sql 文件执行。
    坑：--command 只会跑第一条语句，多行 INSERT 会被静默丢掉（只进 1 条）。"""
    tmp = os.path.join(HERE, "_tmp_board.sql")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(sql if sql.rstrip().endswith(";") else sql + ";")
    try:
        p = subprocess.run(
            ["npx.cmd" if os.name == "nt" else "npx"] + ["-y", "wrangler@latest", "d1", "execute", DB, "--remote", "--json", "--file=" + tmp],
            capture_output=True, text=True, timeout=300, env=os.environ.copy())
        if p.returncode != 0:
            print(p.stdout[-900:])
            print(p.stderr[-900:])
            sys.exit(1)
        return p.stdout
    finally:
        try: os.remove(tmp)
        except Exception: pass


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


def main():
    now = int(time.time() * 1000)
    today = time.strftime("%Y%m%d")

    # 已经在库里的编号（避免 7 天内重复）
    used = set()
    try:
        out = d1("SELECT uid FROM board WHERE uid LIKE 'mock_%'")
        data = json.loads(out)
        rows = data[0]["results"] if isinstance(data, list) else data["results"]
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
    picks = fresh[:remain] if remain > 0 else []

    for k, i in enumerate(picks):
        r = POOL[i]
        created = now - (1 + (k * 3) % 20) * 3600000
        # 点赞 1~99：和「今天来过人数」（真实访客 + 基数）同一量级
        likes = 1 + (i * 37 + k * 11) % 99
        lines.append(
            "INSERT INTO board (uid,uname,nick,anon,av,mood,txt,likes,created,expires,hidden) "
            "VALUES ('mock_%s_%d','','%s',0,%d,'%s','%s',%d,%d,%d,0);" % (
                today, i, esc(r["n"]), r["a"], esc(r["m"]), esc(r["t"]), likes,
                created, created + TTL))

    print("今天插 %d 条" % len(lines))
    d1("\n".join(lines))
    print("done")


if __name__ == "__main__":
    main()
