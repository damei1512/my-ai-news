import os
import json
import datetime
import feedparser
import google.generativeai as genai
import time

# 1. 验证 Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ API Key 未配置")

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-flash-latest'

def get_latest_news():
    print("📡 正在抓取 RSS...")
    rss_urls = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://openai.com/index/rss.xml"
    ]
    articles = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                articles.append(f"标题: {entry.title}\n链接: {entry.link}\n简介: {entry.summary[:150]}")
        except: continue
    return "\n\n---\n\n".join(articles) if articles else "Title: AI update.\nLink: #\nSummary: Daily update active."

def summarize_with_gemini(text_content):
    print(f"🤖 正在呼叫 {MODEL_NAME}...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"请将以下英文新闻生成为中文日报摘要（JSON格式列表）。要求：保留link字段，不要Markdown标记。格式：[ {{ 'tag': '', 'title': '', 'link': '', 'summary': '', 'comment': '' }} ]\n内容：{text_content}"
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text)
    except: return []

if __name__ == "__main__":
    # 1. 获取今天日期和星期
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    day_info = week_map[now.weekday()]

    # 2. 读取现有数据
    history_file = 'news.json'
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
                # 兼容旧版本格式
                if isinstance(all_data, dict) and "news" in all_data: all_data = {}
            except: all_data = {}
    else:
        all_data = {}

    # 3. 抓取并生成今天的新闻
    today_articles = summarize_with_gemini(get_latest_news())
    
    if today_articles:
        all_data[date_str] = {
            "day_info": day_info,
            "articles": today_articles
        }

    # 4. 只保留最近 7 天
    sorted_dates = sorted(all_data.keys(), reverse=True)
    final_data = {d: all_data[d] for d in sorted_dates[:7]}

    # 5. 保存
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 更新成功：{date_str}")
