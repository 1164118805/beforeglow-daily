import io

P = 'scripts/refresh_daily_ai.py'
s = io.open(P, encoding='utf-8').read()

BLOCK = '''
    # ---- 说点（笑话/冷笑话/黑色幽默）+ 每天一句 ----
    try:
        DAY_OUT = "daily_ai.json"
        prev = {}
        if os.path.exists(DAY_OUT):
            try:
                prev = json.load(open(DAY_OUT, encoding="utf-8"))
            except Exception:
                prev = {}

        KIND_SYS = {
            "jokes": ("你是给抖音主播写段子的编剧。写能直接念出口的笑话：短、有反转、生活化，"
                      "不低俗、不冒犯、不点名。输出 JSON 数组，每项一个字符串，不要任何解释。"),
            "cold": ("你是冷笑话高手。写一句话讲完的冷笑话：越冷越好，靠莫名的逻辑错位逗人，"
                     "不涉及人身攻击。输出 JSON 数组，每项一个字符串，不要任何解释。"),
            "black": ("你是写温和黑色幽默的作者。写自嘲式、带点丧但好笑的短句："
                      "不写死亡、疾病、暴力、政治，读者听完会笑一下又有点酸。"
                      "输出 JSON 数组，每项一个字符串，不要任何解释。"),
            "quotes": ("你是疗愈站作者小凉，写给正在硬撑的女主播。温柔、不说教、不喊口号，"
                       "一句话 15-35 字。输出 JSON 数组，每项一个字符串，不要任何解释。"),
        }
        KIND_HINT = {
            "jokes": "给 5 条新的笑话。",
            "cold": "给 5 条新的冷笑话。",
            "black": "给 5 条新的黑色幽默。",
            "quotes": "给 2 句新的。",
        }
        out_day = {"v": 1, "ts": int(time.time()), "date": day}
        any_ok = False
        for key in ("jokes", "cold", "black", "quotes"):
            try:
                got = chat(KIND_SYS[key], KIND_HINT[key], kind, url, model, timeout=90)
                arr = _salvage(got) or []
                if isinstance(arr, dict):
                    arr = arr.get("items") or arr.get("list") or []
                items = [str(x).strip() for x in arr if isinstance(x, str) and str(x).strip()]
                items = [x for x in items if 8 <= len(x) <= 120]
                old = [str(x) for x in (prev.get(key) or [])]
                merged = items + [x for x in old if x not in items]
                out_day[key] = merged[:40]
                if items:
                    any_ok = True
                print("daily", key, "+", len(items))
            except Exception as e:
                print("daily fail", key, repr(e)[:120])
                out_day[key] = prev.get(key) or []
        if any_ok:
            json.dump(out_day, open(DAY_OUT, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            changed.append("daily_ai")
    except Exception as e:
        print("daily_ai fail", repr(e)[:120])

'''

anchor = '    print("done:", changed)'
assert s.count(anchor) == 1, s.count(anchor)
s = s.replace(anchor, BLOCK + anchor)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('inserted')

import ast
ast.parse(io.open(P, encoding='utf-8').read())
print('py ok')
