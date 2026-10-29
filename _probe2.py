import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

start = s.index('CANDIDATES = [')
end = s.index(']\n', start) + 2

new = '''CANDIDATES = [
    ("https://models.github.ai/inference/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/v1/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/inference/v1/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/chat/completions", "openai/gpt-4o-mini"),
    ("https://api.github.ai/models/inference/chat/completions", "openai/gpt-4o-mini"),
    ("https://models.github.ai/inference", "openai/gpt-4o-mini"),
]
'''
s = s[:start] + new + s[end:]

# 探测时把状态码和 body 的前 120 字打出来
old = '''    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")'''
new2 = '''    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "ignore")
        _ct = r.headers.get("content-type", "")'''
if s.count(old) == 1:
    s = s.replace(old, new2)

old3 = '        print("RAW[%s] %s" % (r.status, raw[:300].replace(chr(10), " ")))'
new3 = '        print("RAW[%s][%s] %s" % (r.status, _ct, raw[:200].replace(chr(10), " ")))'
if s.count(old3) == 1:
    s = s.replace(old3, new3)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('probe list updated')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
