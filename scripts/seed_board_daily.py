# -*- coding: utf-8 -*-
"""每天往 D1 的 board 表插 10~20 条留言（云端共用，所有人看到同一批）。

用法：python3 scripts/seed_board_daily.py
需要：CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID（GitHub Actions 里配 secret）
"""
import os, sys, json, time, random, subprocess

DB = "beforeglow-db"
TTL = 7 * 24 * 3600 * 1000
HERE = os.path.dirname(os.path.abspath(__file__))
POOL = json.load(open(os.path.join(HERE, "board_pool.json"), encoding="utf-8"))


def esc(t):
    return str(t).replace("'", "''")


def d1(sql):
    p = subprocess.run(
        ["npx.cmd" if os.name == "nt" else "npx"] + ["-y", "wrangler@latest", "d1", "execute", DB, "--remote", "--json", "--command", sql],
        capture_output=True, text=True, timeout=240, env=os.environ.copy())
    if p.returncode != 0:
        print(p.stdout[-900:])
        print(p.stderr[-900:])
        sys.exit(1)
    return p.stdout


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
    picks = fresh[:n]

    lines = []
    for k, i in enumerate(picks):
        r = POOL[i]
        created = now - (1 + (k * 3) % 20) * 3600000
        likes = 0 if k % 4 == 3 else 2 + (i * 37) % 70
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
