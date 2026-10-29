import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()
bad = "    if not old_map:/n        print(\"::error title=AI 全失败::一条都没生成，先不写文件\")/n        sys.exit(1)/n"
good = ("    if not old_map:" + chr(10) +
        "        print(\"::error title=AI 全失败::一条都没生成，先不写文件\")" + chr(10) +
        "        sys.exit(1)" + chr(10))
if bad in s:
    s = s.replace(bad, good)
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    print('repaired')
else:
    # 兜底：任何 /n 都还原成换行（只在这个文件里）
    if '/n' in s:
        s = s.replace('/n', chr(10))
        io.open(p, 'w', encoding='utf-8', newline='').write(s)
        print('repaired by fallback')
    else:
        print('nothing to fix')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
