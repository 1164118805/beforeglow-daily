import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()
dup = '''if os.environ.get("LLM_BASE_URL"):
    CANDIDATES.insert(0, (os.environ["LLM_BASE_URL"], AI_MODEL))
'''
if dup in s:
    s = s.replace(dup, '')
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    print('dup removed')
else:
    print('no dup')

# 两个工作流：AI 步骤失败不要挡住后面的提交
for wf, step in (('.github/workflows/enrich-topics.yml', '      - name: Enrich topics\n'),
                 ('.github/workflows/refresh-hotmusic.yml', '      - name: Enrich topics (30 天内不重复)\n')):
    t = io.open(wf, encoding='utf-8').read()
    if step + '        continue-on-error: true\n' in t:
        print('already soft', wf)
        continue
    if step in t:
        t = t.replace(step, step + '        continue-on-error: true\n', 1)
        io.open(wf, 'w', encoding='utf-8', newline='').write(t)
        print('soft ok', wf)
    else:
        print('step not found', wf)

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
