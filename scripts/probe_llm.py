#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_llm.py — 十秒钟验证「豆包/任意 OpenAI 兼容」接口通不通

只做一件事：发一条最小请求，把结果原样打出来。
- 不读写任何站点数据
- 不参与每日任务
- 失败会明确告诉你卡在哪一步（DNS / TLS / 401 / 403 / 模型名不对 / 返回不是 JSON）

用法：
    # 1) 只测端点通不通（不需要 key）
    python scripts/probe_llm.py --ping

    # 2) 带 key 跑一次真实调用
    python scripts/probe_llm.py --key <你的key> --model doubao-pro-32k
    # 或者用环境变量（GitHub Actions 就是这么注的）
    LLM_API_KEY=xxx LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3 \
    LLM_MODEL=doubao-pro-32k python scripts/probe_llm.py

退出码：0 = 通，1 = 不通
"""
import argparse, json, os, socket, ssl, sys, time, urllib.error, urllib.request

DEFAULT_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-pro-32k"
UA = "beforeglow-probe/1.0"


def ping(host):
    """只测 TCP + TLS 能不能到，不参与鉴权。"""
    print("① DNS/TCP → %s:443" % host)
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host)
        s = socket.create_connection((host, 443), timeout=8)
        s.close()
        print("   ok  %s → %s  (%dms)" % (host, ip, (time.time() - t0) * 1000))
    except Exception as e:
        print("   FAIL %r" % (e,))
        return False

    print("② TLS → %s" % host)
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((host, 443), timeout=8), server_hostname=host) as ss:
            print("   ok  %s  证书 %s" % (ss.version(), ss.getpeercert().get("notAfter")))
    except Exception as e:
        print("   FAIL %r" % (e,))
        return False
    return True


def call(base, model, key, prompt):
    url = base.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 64,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": UA},
    )
    t0 = time.time()
    print("③ POST %s   model=%s" % (url, model))
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", "ignore")
            print("   HTTP %s  (%dms)  %dB" % (r.status, (time.time() - t0) * 1000, len(raw)))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        print("   HTTP %s  ← 这一步失败" % e.code)
        print("   %s" % detail)
        if e.code == 401:
            print("   → key 不对，或没带上（Authorization: Bearer ...）")
        elif e.code == 403:
            print("   → key 有效但没权限：模型没开通，或者 endpoint 绑错了")
        elif e.code == 404:
            print("   → 模型名/路径不对。方舟的 model 要填「推理接入点 ID」或已开通的模型名")
        return False
    except Exception as e:
        print("   FAIL %r" % (e,))
        return False

    print("④ 解析")
    try:
        d = json.loads(raw)
        txt = d["choices"][0]["message"]["content"]
        print("   ok  模型回：%s" % txt.strip()[:120])
        u = d.get("usage") or {}
        if u:
            print("   usage  input=%s output=%s total=%s" % (u.get("prompt_tokens"), u.get("completion_tokens"), u.get("total_tokens")))
        return True
    except Exception as e:
        print("   FAIL 返回不是预期的 chat.completions 结构：%r" % (e,))
        print("   原文前 300 字：%s" % raw[:300])
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true", help="只测端点通不通，不需要 key")
    ap.add_argument("--base", default=os.environ.get("LLM_BASE_URL") or DEFAULT_BASE)
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL") or DEFAULT_MODEL)
    ap.add_argument("--key", default=os.environ.get("LLM_API_KEY") or "")
    ap.add_argument("--key-file", default="", help="从文件读 key（取第一行非 # 非空的行）")
    ap.add_argument("--prompt", default="只回答两个字：通了")
    a = ap.parse_args()

    if a.key_file and not a.key:
        try:
            for line in open(a.key_file, encoding="utf-8"):
                t = line.strip()
                if t and not t.startswith("#"):
                    a.key = t
                    break
        except Exception as e:
            print("读 key 文件失败：%r" % (e,))

    host = a.base.split("://", 1)[-1].split("/")[0]
    print("目标：%s\n模型：%s\n" % (a.base, a.model))
    if not ping(host):
        print("\n结论：端点都不通，先查网络/代理，跟 key 无关。")
        return 1

    if a.ping:
        print("\n结论：端点可达。要验鉴权，加 --key 再跑一次。")
        return 0

    if not a.key:
        print("\n⑤ 鉴权 → 没给 key")
        print("   跳过。用 --key 或在环境变量里放 LLM_API_KEY。")
        print("\n结论：端点可达，但鉴权未验证。")
        return 1

    ok = call(a.base, a.model, a.key, a.prompt)
    print("\n结论：%s" % ("通了，可以接进每日任务。" if ok else "没通，看上面第几步红的。"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
