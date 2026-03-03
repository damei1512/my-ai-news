#!/usr/bin/env python3
"""快速生成时事新闻（简化版）"""
import os
import json
import datetime
import feedparser
import google.generativeai as genai
import pytz

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY 未设置，请在 .env 文件中配置")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

# 抓取BBC新闻
print("📡 抓取BBC世界新闻...")
feed = feedparser.parse('https://feeds.bbci.co.uk/news/world/rss.xml')
articles = []
for entry in feed.entries[:8]:  # 取前8条
    articles.append({
        "title": entry.title,
        "link": entry.link,
        "summary": entry.get('description', '')[:300]
    })

print(f"✓ 抓取到 {len(articles)} 条新闻")

# 生成中文摘要
print("🤖 生成中文摘要...")
content_parts = []
for i, a in enumerate(articles, 1):
    content_parts.append(f"[{i}] 标题: {a['title']}\n链接: {a['link']}\n简介: {a['summary']}")

content = "\n\n---\n\n".join(content_parts)

prompt = f"""
你是国际新闻主编。请将以下英文国际新闻翻译成中文日报摘要（JSON格式）。

要求：
1. category 字段固定填 "时事"
2. tag 字段填写新闻类型（如战争、冲突、政治、经济等，3-4个字）
3. 翻译title成中文
4. summary 字段：100字以内中文摘要
5. comment 字段：毒舌点评，50字以内中文
6. image 字段留空字符串 ""
7. 只选最重要的5条新闻

JSON格式：
[{{"category": "时事", "tag": "战争", "title": "中文标题", "link": "...", "summary": "中文摘要", "comment": "中文点评", "image": ""}}]

新闻内容：
{content}
"""

response = model.generate_content(prompt)
text = response.text.strip()
if text.startswith("```json"): text = text[7:]
if text.startswith("```"): text = text[3:]
if text.endswith("```"): text = text[:-3]

news_items = json.loads(text)
print(f"✓ 生成 {len(news_items)} 条时事新闻")

# 读取现有news.json
with open('news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取今天的key
today = list(data.keys())[0]

# 添加时事新闻到现有文章列表
data[today]['articles'].extend(news_items)

# 保存
with open('news.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ 已添加到 {today}，现在共 {len(data[today]['articles'])} 篇文章")

# 显示新增的新闻
print("\n新增时事新闻：")
for item in news_items:
    print(f"- [{item['tag']}] {item['title']}")
