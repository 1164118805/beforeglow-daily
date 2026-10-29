import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

# 1) 把单一 URL/模型换成候选链 + 启动探测
old = ('AI_URL = os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference/chat/completions"\n'
       'AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"\n')
new = ('AI_URL = os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference/chat/completions"\n'
       'AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"\n'
       '# 候选端点/模型（第一个探测成功的会被采用）\n'
       'CANDIDATES = [\n'
       '    ("https://models.github.ai/inference/chat/completions", "openai/gpt-4o-mini"),\n'
       '    ("https://models.github.ai/inference/chat/completions", "openai/gpt-4.1-mini"),\n'
       '    ("https://models.github.ai/inference/chat/completions", "gpt-4o-mini"),\n'
       '    ("https://models.inference.ai.azure.com/chat/completions", "gpt-4o-mini"),\n'
       ']\n'
       'if os.environ.get("LLM_BASE_URL"):\n'
       '    CANDIDATES.insert(0, (os.environ["LLM_BASE_URL"], AI_MODEL))\n')
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

# 2) 请求函数：打印原始响应，便于定位
old2 = '''    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))'''
new2 = '''    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
    try:
        d = json.loads(raw)
    except Exception:
        print("RAW[%s] %s" % (r.status, raw[:300].replace(chr(10), " ")))
        raise'''
assert s.count(old2) == 1, s.count(old2)
s = s.replace(old2, new2)

# 3) 启动探测，选中第一个能用的组合
old3 = '''    if not TOKEN:
        print("no token, abort")
        sys.exit(1)'''
new3 = '''    if not TOKEN:
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
        sys.exit(1)'''
assert s.count(old3) == 1, s.count(old3)
s = s.replace(old3, new3)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
