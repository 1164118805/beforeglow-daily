#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只跑 AI 补全：读 hot_topics.json → ai_enrich → 写回。
   用于本地补数据，不重新抓源。用法：
   LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=... python -u scripts/ai_only.py [条数]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh_hot_topics as R

p = os.path.join(os.getcwd(), "hot_topics.json")
d = json.load(open(p, encoding="utf-8"))
lst = d["list"]
n = int(sys.argv[1]) if len(sys.argv) > 1 else len(lst)
lst = lst[:n]
print("待补", len(lst), "条 →", R.AI_URL, R.AI_MODEL, flush=True)
lst = R.ai_enrich(lst)
ok = sum(1 for x in lst if x.get("mean") or x.get("from"))
print("补全成功", ok, "/", len(lst), flush=True)
d["list"] = lst + d["list"][n:]
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("已写回", p, flush=True)
