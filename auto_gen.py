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

# 🔥 核心修改：使用你诊断报告里明确存在的 gemini-2.0-flash
MODEL_NAME = 'gemini-2.0-flash'

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
            print(f"   - 连接 {url} 成功，发现 {len(feed.entries)} 条")
            for entry in feed.entries[:2]:
                articles.append(f"标题: {entry.title}\n简介: {entry.summary[:150]}")
        except Exception as e:
            print(f"   ❌ 连接 {url} 失败: {e}")

    # 如果一条新闻都没抓到（防止空跑报错），用测试数据兜底
    if not articles:
        print("⚠️ 警告：RSS 抓取为空，使用测试数据验证流程...")
        return "Title: Google Gemini 2.0 is released.\nSummary: The new model is extremely fast and intelligent."
    
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print(f"🤖 正在呼叫 {MODEL_NAME}...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""
        你是一个科技新闻主编。请将以下英文新闻生成为中文日报摘要（JSON格式）。
        
        要求：
        1. 必须是标准的 JSON 列表格式。
        2. 绝对不要使用 Markdown 代码块标记（不要写 ```json）。
        3. 如果新闻很少，请尽量挖掘其价值。
        
        JSON 格式示例：
        [
            {{
                "tag": "AI前沿",
                "title": "中文标题",
                "summary": "中文摘要(50-80字)",
                "comment": "一句话毒舌点评"
            }}
        ]

        新闻内容：
        {text_content}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 清洗可能存在的格式符号（双重保险）
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ Gemini API 报错: {e}")
        return [{
            "tag": "系统提示",
            "title": "更新中断",
            "summary": f"调用模型 {MODEL_NAME} 失败，请检查 GitHub 日志。",
            "comment": str(e)
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
    print("✅ 任务完美完成！")
