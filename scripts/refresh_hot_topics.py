#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refresh_hot_topics.py — 多平台热榜 → hot_topics.json（每天 06:30 由 GitHub Actions 跑）

- 抖音（xcvts）、B站（官方 ranking）、微博/知乎（Tophub）稳定抓取
- 抓到的平台用今天的；没抓到的平台保留上一版（保证多平台不全丢）
- 过滤政治/军事/灾难/官媒，只留娱乐生活类
- 连续在榜天数写入 d（用于「持续热」）
"""
import json, os, re, sys, time, datetime, html, urllib.request, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

SOURCES = [
    ("抖音", "https://api.xcvts.cn/api/hotlist/dy"),
    ("B站", "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"),
    ("微博", "tophub:KqndgxeLl9"),
    ("知乎", "tophub:mproPpoq6O"),
    ("小红书", "rebang:xiaohongshu"),
    ("B站", "bili:热梗"),
    ("B站", "bili:什么梗"),
    ("B站", "bili:梗百科"),
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


BILI_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def bili_search(kw, days=3):
    """B站搜索（按发布时间倒序）。梗几乎只出现在二创标题里，热榜抓不到。
    需要先访问首页拿 buvid3 cookie，否则第二次就 412；境外 IP 大概率直接失败，静默跳过。"""
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try:
        op.open(urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent": BILI_UA}), timeout=15).read()
    except Exception:
        pass
    q = urllib.parse.quote(kw)
    u = ("https://api.bilibili.com/x/web-interface/search/type?search_type=video"
         "&keyword=" + q + "&order=pubdate&page=1")
    req = urllib.request.Request(u, headers={"User-Agent": BILI_UA, "Referer": "https://www.bilibili.com/"})
    import json as _j
    d = _j.loads(op.open(req, timeout=20).read().decode("utf-8", "ignore"))
    if d.get("code") != 0:
        raise RuntimeError("bili code %s" % d.get("code"))
    now = time.time()
    out = []
    for it in (d.get("data", {}).get("result") or []):
        pd = int(it.get("pubdate") or 0)
        if pd and now - pd > days * 86400:
            continue
        t = re.sub(r"<[^>]+>", "", it.get("title") or "")
        t = html.unescape(t).strip()
        if t:
            out.append(t)
    return out


def fetch(url):
    if url.startswith("bili:"):
        return bili_search(url.split(":", 1)[1])
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


GENG_NOISE = re.compile(r"【[^】]{1,10}】|\[[^\]]{1,10}\]|（[^）]{0,6}(?:梗|百科|学堂|音乐志)[^）]{0,6}）|\([^)]{0,6}(?:梗|百科)[^)]{0,6}\)")


SENT_PUNC = "，。！？～、：；…,.!?~|｜《》【】「」"


def looks_like_geng(t):
    """B站一堆视频标题会被当成梗：「用最密的热梗，包了一个很多人没接住的黑色寓言」
    「Day1: 一个 AI 给自己装了梗百科，还去训了嗓子」。判断标准很土但有效：
    梗是**词**，不是句子——长度短、没有标点、不是泛称。"""
    v = str(t or "").strip()
    if not v:
        return False
    if len(v) > 14:
        return False
    if any(c in v for c in SENT_PUNC):
        return False
    if re.search(r"梗百科|热梗|什么梗|梗学堂|接不住|不放过", v):
        return False
    return True


def clean_geng_title(t):
    """B站二创标题长这样：「【梗百科】"外公的脑袋不够用"是什么梗，归寂你怎么不多长40个脑袋？」
    要的是里面那个梗本身。顺序很关键：**先按「是什么梗」切，再退回引号**——
    反过来的话，正文里随便一个引号都会把梗顶掉（"草碧青孩是什么梗？中国抽象"自卫摇滚"…" 会切出"自卫摇滚"）。"""
    raw = str(t or "").strip()
    if not raw:
        return raw

    x = GENG_NOISE.sub("", raw).strip()
    x = re.sub(r"^(?:梗百科之|梗百科|热梗百科|梗学堂[:：]?)", "", x).strip()

    BAD_TAIL = "我你他她它的了是，,。、？！?!"

    def ok(v):
        v = v.strip(" ：:，,。.、？！?!「」『』“”\"'")
        if not (2 <= len(v) <= 14):
            return None
        if not re.search(r"[\u4e00-\u9fa5]", v):
            return None
        if v[-1] in BAD_TAIL:          # 明显被切断了（"热梗猜影子，猜猜我"）
            return None
        if "猜猜" in v or "是谁" in v:
            return None
        return v

    # 1) 有「是什么梗 / 是谁 / 什么梗」的，切掉标记及后面的一切
    parts = re.split(r"(?:是什么梗|是啥梗|是什么意思|是什么|是谁啊|是谁|啥梗|什么梗)", x, maxsplit=1)
    if len(parts) > 1:
        v = ok(parts[0])
        if v:
            return v

    # 2) 退一步：引号里的（只在没有标记、或标记前切不出来时才用）
    m = re.search(r"[「『“\"]([^」』”\"]{2,16})[」』”\"]", x)
    if m:
        v = ok(m.group(1))
        if v:
            return v

    # 3) 实在切不出来就原样保留（宁可长，不要错）
    return raw


def titles(d):
    if not d:
        return []
    # 注意：list 要先判，否则 d.get 直接抛 AttributeError（bili: 源就是这样整条挂掉的）
    if isinstance(d, list):
        arr = d
    else:
        arr = d.get("data") or d.get("result") or d.get("list") or []
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
        if "梗" in t:
            t = clean_geng_title(t)
            if not looks_like_geng(t):
                continue          # 「用最密的热梗，包了一个…」这种整句，不是梗
        if t and len(t) <= 40 and len(re.findall(r"[\u4e00-\u9fa5]", t)) >= 3 and not BAD.search(t):
            out.append(t)
    return out


# 兼容两种写法：给完整 endpoint（GitHub Models 那种），或给 base（方舟的 .../api/v3）
AI_URL = (os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference/chat/completions").rstrip("/")
if not AI_URL.endswith("/chat/completions"):
    AI_URL += "/chat/completions"
AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"
AI_SYS = (
    "你是中文网络热梗的核验员，不是作家。任务：判断给定词条是不是热梗，并给出全网实际流通的真实含义。\n"
    "\n【强制输出规则】\n"
    "1 只输出纯 JSON 数组，不要 markdown、不要 ```json、不要任何前置说明或结尾注释。\n"
    "2 每条严格按这 15 个字段，不多不少：\n"
    "   {t,status,real_meaning,misinterpret,source_platform,hot_since,usage_example,tone,scene,o,r,e,a,detail}\n"
    "3 status 只能是 \"ok\" / \"uncertain\" / \"invalid\"：\n"
    "   invalid＝这不是热梗（普通句子、新闻、广告、人名事件、知识问答）；\n"
    "   uncertain＝是梗，但你无法交叉验证它的含义；\n"
    "   ok＝你确定。\n"
    "4 real_meaning：ok 时必填，写「全网实际在用的意思」——禁止按字面脑补翻译。\n"
    "5 misinterpret：存在广为流传的错误释义时才填 {\"wrong\":\"…\",\"why\":\"…\"}，没有就 null（不要空数组、空对象）。\n"
    "6 source_platform：只能从 [\"知乎\",\"小红书\",\"抖音\",\"B站\",\"微博\"] 里挑，数组；不确定就 null。\n"
    "7 hot_since：只能是 \"YYYY-MM\" 或 null，禁止「最近／大概／上月」。\n"
    "8 usage_example：必须是真实网友发言的样子（观众：… 换行 你：…）；**找不到真实例句就 null，绝不自己编**。\n"
    "9 无内容字段一律 null，不要空字符串。\n"
    "10 status=uncertain 时：real_meaning / usage_example / o / r / e / a / detail 全部 null。\n"
    "11 status=invalid 时：除 t、status 外全部 null。\n"
    "12 tone＝词条式 2-6 字（整活／自嘲／调侃／松弛／扎心）。\n"
    "13 scene＝直播适用场景，2-3 个用「、」隔开。\n"
    "14 o 开口 / r 接话 / e 延伸 / a 避坑：各一句，直播能直接念出来。\n"
    "15 detail＝严格六行，用 \\n 分隔，依次以「① 梗是什么」「② 出处来源」「③ 情绪调性」「④ 直播适用场景」「⑤ 避雷禁区」「实操话术：」开头。\n"
    "\n【怎么判断是不是梗】\n"
    "B站＝标题里的「XX是什么梗／XX挑战」、弹幕刷屏词、二创混剪的固定台词；\n"
    "抖音＝动作／口头禅／挑战，常配固定 BGM 或固定镜头；\n"
    "小红书＝生活方式梗（某种吃法／穿搭／仪式感），爱带 emoji 和「谁懂啊」；\n"
    "微博＝热搜词条／超话标题，常是缩写、谐音、人名+事件；\n"
    "知乎＝问题式（「为什么最近都在说XX」）。\n"
    "形态：2-6 字生造词、方言、谐音、错别字变体、影视台词、主播口头禅、动作名。\n"
    "顺序：先判「是不是被反复玩的东西」→ 再判「我认不认识它的来历」。\n"
    "\n【兜底】想自由行文／吐槽／补充说明，一律压制；无论如何都不能跳出 JSON。"
    "信息不足就按规则填 null 和对应 status，不要拒绝输出。本次没有符合条件的条目就返回 []。\n"
)


def _ai_chat(token, titles, sys_prompt=None):
    body = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt or AI_SYS},
            {"role": "user", "content": "话题：" + json.dumps(titles, ensure_ascii=False)},
        ],
        "temperature": 0.8,
        # 每条要写 17 个字段（含 detail 六行），4000 会被截断成半截 JSON
        "max_tokens": 8000,
    }
    # 豆包 seed 系列默认带思考过程：先把 reasoning 跑满再出正文，长结构化输出必超时。
    # 抽字段这种活不需要思考，关掉能快 3 倍（实测 150s 超时 → 55s 出结果）。
    if "volces.com" in AI_URL or "ark.cn" in AI_URL:
        body["thinking"] = {"type": "disabled"}
    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"]


FILL_SYS = (
    "你是中文梗/直播话术编辑。只补三个字段："
    "from=出处（这个梗/词怎么来的；不确定写「暂无明确出处」，不要编）；"
    "ex=使用示范（2-3条对话，先「观众：…」换行再「你：…」）；"
    "stale=时效（该下架写 1，否则 0）。"
    "严格输出 JSON 数组，每项 {t,from,ex,stale}，不要 markdown、不要代码块。"
)


def _ai_fill(token, items):
    by = {x["t"]: x for x in items}
    for i in range(0, len(items), 10):
        chunk = items[i:i + 10]
        titles = [x["t"] for x in chunk]
        try:
            content = _ai_chat(token, titles, FILL_SYS)
            content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
            arr = json.loads(content)
            if isinstance(arr, dict):
                arr = arr.get("items") or arr.get("list") or []
        except Exception as e:
            print("AI fill fail", i, repr(e))
            continue
        n = 0
        for item in arr:
            t = item.get("t")
            x = by.get(t)
            if not x:
                continue
            f = item.get("from")
            e = item.get("ex")
            if isinstance(f, str) and f.strip():
                x["from"] = re.sub(r"^(出处|含义)[：:]\s*", "", f.strip())
            if isinstance(e, str) and e.strip():
                x["ex"] = e.strip()
            if str(item.get("stale")).strip() in ("1", "True", "true"):
                x["stale"] = 1
            n += 1
        print("AI fill", i, "ok", n)


def ai_enrich(lst):
    token = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("AI: no token, keep templates")
        return lst
    by = {x["t"]: x for x in lst}
    for i in range(0, len(lst), 4):
        chunk = lst[i:i + 4]
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

            st = str(item.get("status") or "").strip().lower()

            # 不是梗 —— 直接标记，后面整条剔掉
            if st == "invalid":
                x["invalid"] = 1
                continue

            # 是梗但含义存疑 —— 留标题，其余清空，前端显示「待补充」
            if st != "ok" or not (item.get("real_meaning") or "").strip():
                x["unknown"] = 1
                for _f in ("mean", "from", "tone", "scene", "o", "r", "e", "a", "ex", "detail",
                           "od", "rd", "ed", "ad", "fresh", "mis"):
                    x.pop(_f, None)
                n += 1
                continue

            # —— ok：映射到站内字段 ——
            if x.get("src") == "seed" and str(x.get("mean") or "").strip():
                n += 1
                continue                      # 手写的永远优先，AI 不许碰
            if x.get("lock"):
                # 被锁的词（AI 反复写错）：模型说 ok 也不采信，保持待补充
                x["unknown"] = 1
                for _f in ("mean", "from", "tone", "scene", "o", "r", "e", "a", "ex", "detail", "mis", "fresh"):
                    x.pop(_f, None)
                n += 1
                continue

            x["mean"] = str(item.get("real_meaning")).strip()
            sp = item.get("source_platform")
            if isinstance(sp, list) and sp:
                x["from"] = "来自 " + "、".join([str(y) for y in sp if y])
            hs = item.get("hot_since")
            if isinstance(hs, str) and re.match(r"^\d{4}-\d{2}$", hs.strip()):
                x["fresh"] = hs.strip()
            ue = item.get("usage_example")
            if isinstance(ue, str) and ue.strip():
                x["ex"] = ue.strip()
            mi = item.get("misinterpret")
            if isinstance(mi, dict) and (mi.get("wrong") or mi.get("why")):
                x["mis"] = {"wrong": str(mi.get("wrong") or "").strip(),
                            "why": str(mi.get("why") or "").strip()}
            for key in ("tone", "scene", "o", "r", "e", "a", "detail"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    x[key] = v.strip()
            n += 1
        print("AI batch", i, "ok", n)

    return lst


def fetch_retry(url):
    last = None
    for i in range(2):
        try:
            return fetch(url)
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


ARCHIVE = os.path.join(os.getcwd(), "geng_archive.json")
MEME_MAX = 5000      # 热梗：攒着，越久越值钱
OTHER_MAX = 2000     # 新闻类话题：没必要的留着
KEEP_FIELDS = ("mean", "from", "tone", "scene", "o", "r", "e", "a", "ex", "detail",
               "od", "rd", "ed", "ad", "fresh", "unknown")


def merge_archive(items):
    """把今天这批并进历史库：进过就永不删除，只更新 last / days。
    已补过 AI 字段的不覆盖（省 token），只有新补到的才写进去。"""
    today = datetime.date.today().isoformat()
    try:
        arc = json.load(open(ARCHIVE, encoding="utf-8"))
        if not isinstance(arc, dict):
            arc = {"v": 1, "items": []}
    except Exception:
        arc = {"v": 1, "items": []}
    by = {x.get("t"): x for x in arc.get("items", []) if x.get("t")}

    added = touched = 0
    for it in items:
        t = it.get("t")
        if not t:
            continue
        old = by.get(t)
        if old:
            if old.get("last") != today:
                old["days"] = int(old.get("days") or 1) + 1
                old["last"] = today
                touched += 1
            # 新补到的字段才覆盖，旧的不动
            for f in KEEP_FIELDS:
                if it.get(f) and not old.get(f):
                    old[f] = it[f]
            if it.get("k"):
                old["k"] = it["k"]
            if it.get("h"):
                old["h"] = max(int(old.get("h") or 0), int(it["h"]))
        else:
            row = {"t": t, "first": today, "last": today, "days": 1}
            for f in ("k", "h") + KEEP_FIELDS:
                if it.get(f):
                    row[f] = it[f]
            arc["items"].append(row)
            by[t] = row
            added += 1

    lst = arc.get("items", [])
    lst.sort(key=lambda x: (int(x.get("days") or 1), x.get("last") or ""), reverse=True)
    memes = [x for x in lst if x.get("k") == "热梗"]
    others = [x for x in lst if x.get("k") != "热梗"]
    if len(memes) > MEME_MAX:
        memes = memes[:MEME_MAX]
    if len(others) > OTHER_MAX:
        others = others[:OTHER_MAX]
    lst = memes + others
    arc["items"] = lst
    arc["at"] = today
    arc["total"] = len(lst)
    json.dump(arc, open(ARCHIVE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("archive +%d 新 / %d 天更 / 共 %d" % (added, touched, len(lst)))
    return arc


def vet_hot_geng(lst):
    """交叉验证：热梗再问一遍（低温），两次释义差太多就判定"模型在编"，标 unknown。
    只对热梗做，一天也就几条，成本可忽略。"""
    token = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")
    if not token:
        return lst
    cand = [x for x in lst if x.get("k") == "热梗" and x.get("mean") and x.get("src") != "seed"]
    if not cand:
        return lst
    by = {x.get("t"): x for x in cand}
    titles = [x.get("t") for x in cand][:20]
    try:
        raw = _ai_chat(token, titles)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        arr = json.loads(raw)
        if isinstance(arr, dict):
            arr = arr.get("items") or arr.get("list") or []
    except Exception as e:
        print("vet fail", repr(e))
        return lst

    def grams(s):
        s = re.sub(r"[\s\W]+", "", str(s or ""))
        return set(s[i:i + 2] for i in range(max(0, len(s) - 1)))

    def sim(a, b):
        A, B = grams(a), grams(b)
        if not A or not B:
            return 0.0
        return len(A & B) / float(len(A | B))

    drop = 0
    for it in arr:
        t = it.get("t")
        x = by.get(t)
        if not x:
            continue
        if str(it.get("status") or "").strip().lower() != "ok":
            continue
        a, b = x.get("mean") or "", it.get("real_meaning") or ""
        if not b.strip():
            continue
        # 两次措辞可以不同，但语义要重合；重合度低于 0.32 判为"说法对不上"
        if sim(a, b) < 0.32:
            x["unknown"] = 1
            for f in ("mean", "from", "tone", "scene", "o", "r", "e", "a", "ex", "detail", "od", "rd", "ed", "ad"):
                x.pop(f, None)
            x["disputed"] = [x.get("t"), a[:30], b[:30]]
            drop += 1
    if drop:
        print("vet: %d 条两次说法对不上，已标「待补充」" % drop)
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
                f = {k: x[k] for k in ("o", "r", "e", "a", "od", "rd", "ed", "ad",
                                       "from", "mean", "tone", "scene", "ex", "detail", "fresh") if x.get(k)}
                if f:
                    prev_fields[x.get("t", "")] = f
        except Exception as e:
            print("prev read fail", e)

    fetched = {}
    counts = {}
    for pi, (p, url) in enumerate(SOURCES):
        try:
            ts = titles(fetch_retry(url))
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

    # ── 手工「梗种」：每天无条件并入，优先级最高 ──
    # 为什么必须有这个：热榜是「新闻」，梗活在评论区与二创标题里，
    # 而 GitHub Actions 在境外，抖音/微博/小红书的一手接口全被墙，只能靠第三方聚合，
    # 聚合出来的又全是新闻。所以「闪身步」这类梗，光靠抓永远抓不到，只能人工播一条。
    seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geng_seed.json")
    try:
        seed = json.load(open(seed_path, encoding="utf-8")).get("items") or []
    except Exception as e:
        seed = []
        print("seed read fail", repr(e))
    if seed:
        have = {x.get("t") for x in lst}
        add = []
        for i, it in enumerate(seed):
            t = (it.get("t") or "").strip()
            if not t:
                continue
            if t in have:
                for x in lst:
                    if x.get("t") == t:
                        x["k"] = "热梗"
                        x["h"] = max(int(x.get("h", 0) or 0), 900000 - i)
                continue
            row = {"p": "手动", "t": t, "h": 900000 - i, "d": 1, "k": "热梗", "src": "seed"}
            # 手写字段直接进库，AI 不再碰它们
            for _f in ("mean", "from", "tone", "scene", "o", "r", "e", "a", "ex", "detail", "lock", "mis"):
                if it.get(_f):
                    row[_f] = it[_f]
            if it.get("note"):
                row["seed_note"] = it["note"]
            add.append(row)
        if add:
            lst = add + lst
        print("seed merged", len(add), "new /", len(seed), "total")
    try:
        lst = ai_enrich(lst)
        token = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")
        if token:
            missing = [x for x in lst if not x.get("from") or not x.get("ex")]
            if missing:
                print("AI second pass for", len(missing), "items")
                _ai_fill(token, missing)
    except Exception as e:
        print("AI enrich fail", repr(e))
    for x in lst:
        if x.get("p") == "手动":
            x["k"] = "热梗"
            x.pop("seed_note", None)
    # 手工种子不受 stale 影响：模型说"过时"也不删，宁可留着
    _stale = [x for x in lst if x.get("stale") and x.get("p") != "手动"]
    if _stale:
        print("drop stale", len(_stale), [x.get("t") for x in _stale][:6])
        lst = [x for x in lst if not x.get("stale")]
    _ai_ok = sum(1 for x in lst if x.get("from") or x.get("mean"))
    if _ai_ok == 0:
        print("::warning title=AI 没产出::这次没有得到任何 from/mean 字段，检查 models 权限或 LLM_API_KEY")
    else:
        print("AI fields on %d/%d items" % (_ai_ok, len(lst)))
    # 没跑成 AI（没 token / 全失败）时，只发布「有释义的」和「手工种子」。
    # 热榜生标题直接端给用户就是一堆句子（"用最密的热梗，包了一个…"），宁可少，不要脏。
    _ai_ok_now = sum(1 for x in lst if x.get("mean"))
    if _ai_ok_now == 0:
        _before = len(lst)
        lst = [x for x in lst if x.get("src") == "seed" or x.get("mean")]
        print("::warning title=这次没有 AI::只发布 %d 条（原有 %d 条未补释义，已挡在门外）" % (len(lst), _before))

    _bad = [x for x in lst if x.get("invalid")]
    if _bad:
        print("drop invalid", len(_bad), [x.get("t") for x in _bad][:5])
        lst = [x for x in lst if not x.get("invalid")]
    # 交叉验证：新 schema 已经用 status=uncertain 自己示弱了，再叠一层会误删好答案，
    # 默认关掉；要开就把下一行注释去掉（成本翻倍，只对热梗）。
    # lst = vet_hot_geng(lst)
    try:
        merge_archive(lst)
    except Exception as e:
        print("archive fail", repr(e))
    out = {"v": 1, "at": datetime.date.today().isoformat(), "ts": int(time.time()), "note": "全网多平台热榜（每天 06:30 更新，AI 整理）", "sources": counts, "list": lst[:80]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("saved", len(out["list"]), "from", counts)

    # ── 往期归档：每天存一份，站点上能翻前几天的 ──
    try:
        day = out.get("at") or datetime.date.today().isoformat()
        os.makedirs("hot", exist_ok=True)
        # 列表和详情分开存：带 detail 的整份是 41KB，国内链路经常传一半就断；
        # 列表只留标题/类型/平台/释义（约 10KB），详情单独一份，点开时再取。
        slim, det = [], {}
        for x in out["list"]:
            t = x.get("t")
            if x.get("detail"):
                det[t] = x["detail"]
            slim.append({k: x[k] for k in ("t", "k", "p", "mean", "from", "h", "fresh")
                         if x.get(k) not in (None, "")})
        arch = dict(out)
        arch["list"] = slim
        json.dump(arch, open(os.path.join("hot", day + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        json.dump({"_v": 1, "map": det},
                  open(os.path.join("hot", day + "-d.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        idx_p = os.path.join("hot", "index.json")
        days = []
        if os.path.exists(idx_p):
            try:
                days = json.load(open(idx_p, encoding="utf-8")).get("days") or []
            except Exception:
                days = []
        days = sorted(set([day] + list(days)), reverse=True)[:90]
        json.dump({"v": 1, "days": days}, open(idx_p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        # 只留最近 90 个文件，别把仓库撑大
        for f in os.listdir("hot"):
            if f.endswith("-d.json"):
                continue          # 详情文件跟着列表一起留，别被当过期清掉
            if f.endswith(".json") and f != "index.json" and f[:-5] not in days:
                try:
                    os.remove(os.path.join("hot", f))
                except Exception:
                    pass
        print("archived", day, "days", len(days))
    except Exception as e:
        print("archive day fail", repr(e))

    return 0


if __name__ == "__main__":
    sys.exit(main())
