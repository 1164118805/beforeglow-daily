import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

# 1) 候选里加 DDG（免 key，SSE）
old = 'CANDIDATES.append(("https://text.pollinations.ai/openai", "mistral"))\n'
new = ('CANDIDATES.append(("https://text.pollinations.ai/openai", "mistral"))\n'
       'CANDIDATES.append(("ddg", "gpt-4o-mini"))\n')
if s.count(old) == 1:
    s = s.replace(old, new)
    print('ddg candidate added')

# 2) 探测/批处理按 url 判断 kind
old2 = '''            AI_URL, AI_MODEL = url, model
            got = ai_batch([{"t": "测试", "k": "词汇", "o": "你好", "r": "你好呀"}], {}, timeout=40)'''
new2 = '''            AI_URL, AI_MODEL = url, model
            _kind = "ddg" if url == "ddg" else "openai"
            got = ai_batch([{"t": "测试", "k": "词汇", "o": "你好", "r": "你好呀"}], {}, timeout=45, kind=_kind)'''
assert s.count(old2) == 1
s = s.replace(old2, new2)

old3 = '                got = ai_batch(chunk, old_map)'
new3 = '                got = ai_batch(chunk, old_map, timeout=55, kind=_KIND)'
assert s.count(old3) == 1
s = s.replace(old3, new3)

# 3) _KIND 全局
old4 = 'AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"'
new4 = 'AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"\n_KIND = "openai"'
assert s.count(old4) == 1
s = s.replace(old4, new4)

old5 = '''            if got:
                picked = (url, model)'''
new5 = '''            if got:
                picked = (url, model)
                globals()["_KIND"] = _kind'''
assert s.count(old5) == 1
s = s.replace(old5, new5)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('wired')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
