import os
import json
import datetime
import feedparser
import google.generativeai as genai

# 1. 验证 Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ API Key 未配置")

genai.configure(api_key=GEMINI_API_KEY)

# 2. 核心配置：使用目前最主流、最便宜的 Flash 模型
# 如果这个还报错，说明 Google 账号本身有限制
MODEL_NAME = 'gemini-1.5-flash' 

def get_latest_news():
    print("📡 正在抓取 RSS...")
    rss_urls = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss"
    ]
    
    articles = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            print(f"   - 连接 {url} 成功，发现 {len(feed.entries)} 条")
            for entry in feed.entries[:2]:
                articles.append(f"标题: {entry.title}\n简介: {entry.summary[:150]}")
        except Exception as e:
            print(f"   ❌ 连接 {url} 失败: {e}")

    # 如果抓不到（比如网络问题），用一条备用新闻测试 API 是否通畅
    if not articles:
        print("⚠️ 警告：RSS 抓取为空，使用测试数据验证 API...")
        return "Title: AI is advancing rapidly.\nSummary: New models are released every day."
    
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print(f"🤖 正在呼叫 {MODEL_NAME}...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""
        你是一个科技新闻编辑。请将以下英文新闻生成为中文日报摘要（JSON格式）。
        
        要求：
        1. 必须是合法的 JSON 列表。
        2. 不要包含 Markdown 标记（不要写 ```json）。
        
        JSON 格式示例：
        [
            {{
                "tag": "AI新闻",
                "title": "中文标题",
                "summary": "中文摘要",
                "comment": "一句话点评"
            }}
        ]

        新闻内容：
        {text_content}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 清洗可能存在的格式符号
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ Gemini API 报错: {e}")
        # 返回一个报错卡片，让你知道哪里出了问题
        return [{
            "tag": "系统提示",
            "title": "API 调用异常",
            "summary": f"错误详情: {str(e)}",
            "comment": "请检查 API Key 权限或模型名称"
        }]

if __name__ == "__main__":
    raw_news = get_latest_news()
    news_data = summarize_with_gemini(raw_news)
    
    # 写入文件
    output = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("✅ 任务完成，news.json 已生成")
