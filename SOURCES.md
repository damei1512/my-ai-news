# 美时美刻 - 信息渠道清单

## 📊 当前分类体系（3大分类）

### 1️⃣ 科技&数码
**覆盖内容：** 科技新闻、AI/大模型、AI Agent、数码产品、芯片算力、创业公司

**RSS信源：**
| 类型 | 来源 |
|-----|------|
| 国内科技 | 36氪、爱范儿、品玩、机器之心 |
| 国际科技 | TechCrunch AI、Wired AI、The Verge AI、Engadget |
| AI公司官方 | OpenAI博客、Anthropic博客 |
| 开发者社区 | Hacker News、LessWrong、Reddit r/LocalLLaMA |
| AI Agent框架 | LangChain博客、AutoGen GitHub、AutoGPT GitHub、CrewAI GitHub、Coze博客 |

**X (Twitter) 账号：**
- LangChain官方 (@langchain)
- CrewAI官方 (@crewai_inc)
- CrewAI CEO (@joaomdmoura)
- Andrej Karpathy (@karpathy)
- Sam Altman (@sama)
- Rowan Cheung (@rowancheung) - AI新闻聚合
- 马斯克 (@elonmusk)

**微博账号：**
- 闫俊杰 (MiniMax)
- 杨植麟 (月之暗面/Kimi)
- 李志飞 (出门问问)
- 王小川 (百川智能)
- 雷军 (小米)

---

### 2️⃣ 游戏+影视
**覆盖内容：** 游戏发售/评测/预告、主机资讯、电竞、影视动态

**RSS信源：**
| 来源 | 说明 |
|-----|------|
| IGN | 游戏评测、预告 |
| GameSpot | 游戏新闻 |
| 机核网 | 国内游戏文化 |
| Engadget | 含游戏数码内容 |

**补充渠道：** 可通过RSSHub抓取
- Steam新品/销量榜
- PlayStation/Xbox官方博客
- Netflix新剧发布

---

### 3️⃣ 时事&热点
**覆盖内容：** 国际时事、经济政策、社会热点、国内热榜

**RSS信源：**
| 类型 | 来源 |
|-----|------|
| 国际新闻 | BBC World、Reuters |
| 国内热榜 | 即刻热门话题 (RSSHub) |

**补充渠道：** 可通过RSSHub抓取
- 知乎热榜
- 微博热搜
- B站热门
- 抖音热门

---

## ⏰ 更新频率

**自动更新：** 北京时间 8:00 / 10:00 / 12:00 / 14:00 / 16:00 / 18:00 / 20:00
（每2小时一次，早8点至晚8点，共7次/天）

**手动触发：** 通过 `trigger_workflow.py` 脚本随时触发

---

## 🔧 技术架构

1. **数据抓取** - `auto_gen.py` (RSS + X + 微博)
2. **内容处理** - DeepSeek API (摘要、点评、翻译)
3. **自动发布** - GitHub Actions (定时触发)
4. **前端展示** - 静态HTML (GitHub Pages)

---

## 📈 待优化项

- [ ] X (Twitter) RSSHub源不稳定，考虑自建或替换
- [ ] 微博RSS源需RSSHub支持
- [ ] 可考虑添加YouTube频道RSS（游戏预告片）
- [ ] 影视内容可扩展：豆瓣热门、IMDb等
