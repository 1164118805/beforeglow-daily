import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

old = 'CANDIDATES.append(("https://models.github.ai/inference/chat/completions", AI_MODEL))\n'
new = ('CANDIDATES.append(("https://models.github.ai/inference/chat/completions", AI_MODEL))\n'
       '# 无 key 的免费兜底（OpenAI 兼容）\n'
       'CANDIDATES.append(("https://text.pollinations.ai/openai", "openai"))\n'
       'CANDIDATES.append(("https://text.pollinations.ai/openai", "mistral"))\n')
assert s.count(old) == 1
s = s.replace(old, new)

# 探测与批处理都要求 JSON；pollinations 有时会带 ```json，已在 ai_batch 里 strip
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('candidates added')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
