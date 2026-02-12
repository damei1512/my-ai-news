import os
import json
import datetime
import feedparser
import google.generativeai as genai

# 安全获取 API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("API Key 未配置！请在 GitHub Secrets 中配置 GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# 你的 RSS 订阅源（可以随心加）
RSS_URLS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://openai.com/index/rss.xml"
]

def get_latest_news():
    print("正在抓取 RSS...")
    articles = []
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            print(f"源 {url} 抓取成功，共 {len(feed.entries)} 条")
            # 每个源取前 2 条最新的，避免太长
            for entry in feed.entries[:2]:
                articles.append(f"标题: {entry.title}\n简介: {entry.summary[:150]}")
        except Exception as e:
            print(f"源 {url} 出错: {e}")
            
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print("正在呼叫 Gemini 进行分析...")
    # 使用 Gemini 1.5 Flash 模型，速度快且便宜
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    你是一个毒舌但专业的科技博主。请阅读以下从 RSS 抓取的英文 AI 新闻片段，生成一份中文日报数据。
    
    要求：
    1. 挑选出 4-5 个最有价值的新闻。
    2. 必须输出为标准的 JSON 格式。
    3. 不要使用 Markdown 代码块标记（即不要写 ```json ），直接输出 JSON 内容。
    4. JSON 结构如下：
    [
        {{
            "tag": "分类标签(如:大模型/硬件/融资)",
            "title": "中文标题(吸引人一点)",
            "summary": "简练的新闻概括(中文, 80字以内)",
            "comment": "你的个人点评(一针见血, 可以幽默或犀利)"
        }}
    ]

    待处理新闻：
    {text_content}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # 双重保险：去掉可能存在的 markdown 标记
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text)
    except Exception as e:
        print(f"Gemini 生成出错: {e}")
        return []

if __name__ == "__main__":
    raw_news = get_latest_news()
    if not raw_news:
        print("没有抓取到新闻，跳过更新。")
        exit(0)
        
    news_data = summarize_with_gemini(raw_news)
    
    if news_data:
        output = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "news": news_data
        }
        
        with open('news.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("news.json 生成成功！")
    else:
        print("生成数据为空，未写入文件。")
