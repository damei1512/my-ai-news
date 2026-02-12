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

# 🔥 核心修改：换用你列表中存在的、最稳定的 1.5 Flash 版本
# 这个版本通常有每天 1500 次的免费额度，绝对够用
MODEL_NAME = 'gemini-1.5-flash-latest'

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

    # 兜底测试数据
    if not articles:
        print("⚠️ 警告：RSS 抓取为空，使用测试数据...")
        return "Title: AI is evolving.\nSummary: Google Gemini provides free API for developers."
    
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
        3. 翻译准确，点评犀利。
        
        JSON 格式示例：
        [
            {{
                "tag": "AI前沿",
                "title": "中文标题",
                "summary": "中文摘要",
                "comment": "一句话点评"
            }}
        ]

        新闻内容：
        {text_content}
        """
        
        # 增加一个 5 秒延迟，防止触发谷歌的“连点器”保护
        time.sleep(5)
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 清洗数据
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ Gemini API 报错: {e}")
        return [{
            "tag": "系统提示",
            "title": "更新中断",
            "summary": f"模型 {MODEL_NAME} 调用受限，请检查配额。",
            "comment": str(e)
        }]

if __name__ == "__main__":
    raw_news = get_latest_news()
    news_data = summarize_with_gemini(raw_news)
    
    output = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("✅ 任务完成")
