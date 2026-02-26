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
        "https://www.pingwest.com/feed",  # 品玩
        "https://www.jiqizhixin.com/rss", # 机器之心
    ],
    "数码": [
        "https://www.engadget.com/rss.xml",
        "https://www.ifanr.com/feed",
    ],
    "游戏": [
        "https://www.ign.com/rss/articles/feed",
        "https://www.gamespot.com/feeds/news/",
        "https://www.gcores.com/rss",  # 机核
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

# ================= 关键词白名单 =================
# 只有标题/摘要包含这些关键词的文章才会保留
KEYWORD_WHITELIST = {
    "科技": ["芯片", "半导体", "融资", "IPO", "收购", "上市", "苹果", "谷歌", "微软", "英伟达", "华为", "小米", "特斯拉", "SpaceX", "OpenAI", "Anthropic", "AI", "人工智能", "大模型"],
    "数码": ["手机", "相机", "笔记本", "平板", "手表", "耳机", "评测", "体验", "发布", "iPhone", "Android", "摄影"],
    "游戏": ["Switch", "PlayStation", "Xbox", "Steam", "手游", "网游", "DLC", "任天堂", "索尼", "微软", "销量", "发售"],
    "时事": ["经济", "政策", "贸易", "关税", "制裁", "选举", "战争", "冲突", "疫情", "气候变化"],
    "AI": ["ChatGPT", "Claude", "Gemini", "Llama", "大模型", "LLM", "生成式AI", "AIGC", "算力", "GPU", "Agent", "多模态", "AGI", "Prompt", "微调", "训练"]
}

def filter_by_keywords(articles, category):
    """按关键词过滤文章"""
    keywords = KEYWORD_WHITELIST.get(category, [])
    if not keywords:
        return articles
    
    filtered = []
    for article in articles:
        text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
        if any(kw.lower() in text for kw in keywords):
            filtered.append(article)
    
    # 记录过滤信息
    if len(filtered) < len(articles):
        print(f"   📝 关键词过滤: {len(articles)} → {len(filtered)} 篇")
    
    return filtered

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
    
    # 关键词过滤
    articles = filter_by_keywords(articles, category)
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

    all_articles = []
    
    # ========== 1. 抓取 RSS 源 ==========
    print("=" * 50)
    print("📡 阶段1: 抓取 RSS 源")
    print("=" * 50)
    
    for category, urls in RSS_SOURCES.items():
        raw_news = fetch_news_by_category(category, urls)
        if raw_news:
            summarized = summarize_with_gemini(category, raw_news)
            all_articles.extend(summarized)
        time.sleep(1)
    
    # ========== 2. 抓取微博大V ==========
    print("\n" + "=" * 50)
    print("📱 阶段2: 抓取微博大V")
    print("=" * 50)
    
    try:
        from weibo_fetcher import fetch_all_weibo
        weibo_articles = fetch_all_weibo()
        if weibo_articles:
            # 对微博内容也做AI总结
            print("\n🤖 正在总结微博内容...")
            for article in weibo_articles:
                # 简化处理：直接用原文，加AI点评
                article['comment'] = f"【{article['source_name']}微博】大佬发话"
            all_articles.extend(weibo_articles)
    except Exception as e:
        print(f"⚠️ 微博抓取失败: {e}")
    
    # ========== 3. 保存数据 ==========
    print("\n" + "=" * 50)
    print("💾 阶段3: 保存数据")
    print("=" * 50)
    
    if all_articles:
        archive_data[today_date] = {
            "week": today_week,
            "articles": all_articles
        }
        print(f"✅ 今日共 {len(all_articles)} 条新闻")
        
        # 分类统计
        from collections import Counter
        cat_stats = Counter([a.get('category', '未知') for a in all_articles])
        print("📊 分类统计:")
        for cat, count in cat_stats.most_common():
            print(f"   {cat}: {count}条")
    
    # 7天滚动清洗
    sorted_dates = sorted(archive_data.keys(), reverse=True)
    final_data = {d: archive_data[d] for d in sorted_dates[:7]}
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 完成！已保存到 {history_file}")
