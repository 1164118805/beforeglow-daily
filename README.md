# beforeglow-daily

给「发光前夜」网站每天自动更新的抖音热歌榜数据。

- 每天 **06:30（北京时间）** 由 GitHub Actions 自动抓取抖音热歌榜
- 生成 `hotmusic.json`（按 暖场 / 互动 / 情绪 / 卡点 / 纯音 / 下播 分类）
- 通过 jsDelivr 提供给网站读取：
  `https://cdn.jsdelivr.net/gh/1164118805/beforeglow-daily@main/hotmusic.json`

文件说明：

| 文件 | 用途 |
| --- | --- |
| `scripts/refresh_hotmusic.py` | 抓榜 + 分类 + 写出 hotmusic.json |
| `.github/workflows/refresh-hotmusic.yml` | 每天 06:30 的定时任务 |
| `hotmusic.json` | 生成出来的榜单数据 |

> 本仓库只包含「抓公开榜单的脚本」和「歌名列表」，不含任何账号、密码或密钥。
> 网站的源码与令牌都不在这里。
