import os
import json
import datetime
import feedparser
import google.generativeai as genai

# 获取 Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ 错误：API Key 没找到！请检查 Secrets 设置。")

print(f"✅ API Key 读取成功 (前5位): {GEMINI_API_KEY[:5]}...")
genai.configure(api_key=GEMINI_API_KEY)

# 备用测试数据 (防止 RSS 被墙导致流程中断)
BACKUP_NEWS = """
Title: Artificial Intelligence takes over the world
Summary: In a shocking turn of events, AI has decided to run all coffee machines globally.
"""

def get_latest_news():
    print("📡 正在尝试抓取 RSS...")
    rss_urls = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss"
    ]
    
    articles = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            print(f"   - 正在连接 {url}...")
            if feed.entries:
                print(f"     ✅ 成功！获取到 {len(feed.entries)} 条")
                for entry in feed.entries[:2]:
                    articles.append(f"标题: {entry.title}\n简介: {entry.summary[:150]}")
            else:
                print("     ⚠️ 连接成功但没内容")
        except Exception as e:
            print(f"     ❌ 连接失败: {e}")

    if not articles:
        print("⚠️ 警告：所有 RSS 都抓取失败，使用【测试数据】继续运行...")
        return BACKUP_NEWS
    
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print("🤖 正在呼叫 Gemini 1.5 Flash...")
    # 尝试使用更稳定的模型名称
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    请将以下新闻生成为 JSON 格式的中文摘要。
    如果新闻是英文的，请翻译并总结。
    
    JSON 格式要求：
    [
        {{
            "tag": "科技",
            "title": "标题",
            "summary": "摘要",
            "comment": "你的点评"
        }}
    ]

    新闻内容：
    {text_content}
    """
    
    try:
        response = model.generate_content(prompt)
        print("✅ Gemini 响应成功！")
        
        # 清洗数据
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
    except Exception as e:
        print(f"❌ Gemini API 致命错误: {e}")
        # 如果出错，生成一条报错新闻，保证流程不红灯
        return [{
            "tag": "报错",
            "title": "自动更新出错",
            "summary": f"错误详情: {str(e)}",
            "comment": "请检查 GitHub Actions 日志"
        }]

if __name__ == "__main__":
    raw_news = get_latest_news()
    news_data = summarize_with_gemini(raw_news)
    
    # 强制写入文件，不管有没有数据
    output = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("💾 news.json 文件写入完成！")
