#!/usr/bin/env python3
"""快速生成热榜内容（简化版）"""
import os
import json
import datetime
import feedparser
import google.generativeai as genai
import pytz
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY 未设置，请在 .env 文件中配置")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

# 尝试多个热榜源
hot_sources = [
    ("微博热搜", "https://rsshub.rssforever.com/weibo/search/hot"),
    ("百度热搜", "https://rsshub.rssforever.com/baidu/topwords/"),
]

articles = []
for name, url in hot_sources:
    print(f"📡 尝试抓取{name}...")
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:  # 每个源取前5条
            articles.append({
                "source": name,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get('description', entry.title)[:200]
            })
        print(f"  ✓ 获取 {len(feed.entries[:5])} 条")
        if len(articles) >= 8:
            break
    except Exception as e:
        print(f"  ✗ 失败: {e}")

if not articles:
    print("⚠️ 所有热榜源都失败了，使用备用内容")
    # 备用：直接生成一些基于近期热点的话题
    backup_topics = [
        {"title": "iPhone 17e发布：国补后3999元起支持eSIM", "tag": "数码"},
        {"title": "MWC 2026：vivo X300 Ultra亮相，AI视频成新战场", "tag": "科技"},
        {"title": "AI眼镜大战：阿里千问进军智能硬件", "tag": "AI"},
        {"title": "GTA6发布日期确定：2026年5月开启预售", "tag": "游戏"},
        {"title": "国产AI大模型降价潮：价格战愈演愈烈", "tag": "AI"},
    ]
    for t in backup_topics:
        articles.append({
            "source": "综合热点",
            "title": t["title"],
            "link": "#",
            "summary": t["title"]
        })

print(f"\n📊 共获取 {len(articles)} 条热榜内容")

# 生成热榜摘要
print("🤖 生成热榜摘要...")
content_parts = []
for i, a in enumerate(articles[:8], 1):  # 最多8条
    content_parts.append(f"[{i}] 来源: {a['source']}\n标题: {a['title']}\n简介: {a['summary']}")

content = "\n\n---\n\n".join(content_parts)

prompt = f"""
你是社交媒体热点主编。请将以下热门话题整理成中文热榜摘要（JSON格式）。

要求：
1. category 字段固定填 "热榜"
2. tag 字段填写话题类型（如数码、科技、AI、游戏、社会、娱乐等，2-4个字）
3. 保持原标题或稍作优化
4. summary 字段：80字以内，说明为什么上热搜
5. comment 字段：犀利点评，40字以内，要有网感
6. image 字段留空字符串 ""
7. 选最有话题性的5-8条

JSON格式：
[{{"category": "热榜", "tag": "数码", "title": "标题", "link": "...", "summary": "摘要", "comment": "点评", "image": ""}}]

热门内容：
{content}
"""

try:
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]

    news_items = json.loads(text)
    print(f"✓ 生成 {len(news_items)} 条热榜内容")

    # 读取现有news.json
    with open('news.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 获取今天的key
    today = list(data.keys())[0]

    # 添加热榜到现有文章列表
    data[today]['articles'].extend(news_items)

    # 保存
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已添加到 {today}，现在共 {len(data[today]['articles'])} 篇文章")

    # 显示新增的热榜
    print("\n新增热榜：")
    for item in news_items:
        print(f"- [{item['tag']}] {item['title']}")
        
except Exception as e:
    print(f"❌ 生成失败: {e}")
