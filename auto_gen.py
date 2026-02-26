import os
import json
import datetime
import feedparser
import google.generativeai as genai
import time
import pytz

# ================= 配置区 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ API Key 未配置")

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-flash-latest'

# ================= RSS 源配置 =================
# 按分类组织的 RSS 源
RSS_SOURCES = {
    "科技": [
        "https://36kr.com/feed",
        "https://www.ifanr.com/feed",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ],
    "数码": [
        "https://www.engadget.com/rss.xml",
        "https://www.ifanr.com/feed",
    ],
    "游戏": [
        "https://www.ign.com/rss/articles/feed",
        "https://www.gamespot.com/feeds/news/",
    ],
    "时事": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.reutersagency.com/feed/?taxonomy=markets&post_type=reuters-best",
    ],
    "AI": [
        "https://openai.com/index/rss.xml",
        "https://www.anthropic.com/rss.xml",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ]
}

# ================= 核心逻辑 =================

def get_current_date_info():
    """获取北京时间日期和星期"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz)
    date_str = now.strftime("%Y-%m-%d")
    week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    week_str = week_map[now.weekday()]
    return date_str, week_str

def fetch_news_by_category(category, urls):
    """抓取指定分类的新闻"""
    print(f"📡 [{category}] 正在抓取 RSS 源...")
    articles = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            print(f"   ✓ {url}")
            for entry in feed.entries[:3]:  # 每个源取前3条
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get('summary', '')[:300]
                })
        except Exception as e:
            print(f"   ❌ {url} - {e}")
    return articles

def summarize_with_gemini(category, articles):
    """使用 Gemini 对新闻进行分类总结"""
    if not articles:
        return []
    
    print(f"🤖 [{category}] 正在生成摘要...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        content = "\n\n---\n\n".join([
            f"标题: {a['title']}\n链接: {a['link']}\n简介: {a['summary']}"
            for a in articles
        ])
        
        prompt = f"""
你是一个科技主编。请将以下{category}类新闻生成为中文日报摘要（JSON格式）。

【核心要求】
1. category 字段必须填 "{category}"
2. tag 字段填写新闻的子标签（如大模型、芯片、游戏等）
3. 保留原文 Link
4. 输出纯 JSON 列表，无 Markdown

JSON 格式示例：
[
    {{
        "category": "{category}",
        "tag": "子标签",
        "title": "中文标题",
        "link": "https://...",
        "summary": "中文摘要（100字以内）",
        "comment": "毒舌点评（50字以内）"
    }}
]

新闻内容：
{content}
"""
        
        time.sleep(1)
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 清理 Markdown 代码块
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ [{category}] API 错误: {e}")
        return []

if __name__ == "__main__":
    today_date, today_week = get_current_date_info()
    history_file = 'news.json'
    
    # 加载历史数据
    archive_data = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
        except:
            pass

    # 按分类抓取和生成
    all_articles = []
    for category, urls in RSS_SOURCES.items():
        raw_news = fetch_news_by_category(category, urls)
        if raw_news:
            summarized = summarize_with_gemini(category, raw_news)
            all_articles.extend(summarized)
        time.sleep(1)  # 避免 API 限流
    
    # 保存今日数据
    if all_articles:
        archive_data[today_date] = {
            "week": today_week,
            "articles": all_articles
        }
        print(f"✅ 已生成 {len(all_articles)} 条新闻")
    
    # 7天滚动清洗
    sorted_dates = sorted(archive_data.keys(), reverse=True)
    final_data = {d: archive_data[d] for d in sorted_dates[:7]}
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 完成！已保存到 {history_file}")
