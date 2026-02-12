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

# ================= 核心逻辑 =================

def get_current_date_info():
    """获取北京时间日期和星期"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz)
    date_str = now.strftime("%Y-%m-%d")
    week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    week_str = week_map[now.weekday()]
    return date_str, week_str

def get_latest_news():
    print("📡 正在抓取全球 RSS 源...")
    rss_urls = [
        # --- 国外源 ---
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://openai.com/index/rss.xml",
        
        # --- 国内源 (新增) ---
        "https://36kr.com/feed",  # 36Kr (包含国内 AI 投融资和产品动态)
        "https://www.ifanr.com/feed", # 爱范儿 (较多 AI 硬件和应用报道)
    ]
    
    articles = []
    for url in rss_urls:
        try:
            # 设置超时防止卡死
            feed = feedparser.parse(url)
            print(f"   - 连接 {url} 成功")
            
            # 每个源只取前 2 条，防止 Token 爆炸
            for entry in feed.entries[:2]:
                articles.append(f"标题: {entry.title}\n链接: {entry.link}\n简介: {entry.summary[:200]}")
        except Exception as e:
            print(f"   ❌ 连接 {url} 失败: {e}")

    if not articles:
        return "Title: System Update\nLink: #\nSummary: No RSS updates found today."
    
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print(f"🤖 正在呼叫 {MODEL_NAME} 进行区域分类与总结...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""
        你是一个科技主编。请将以下全球新闻生成为中文日报摘要（JSON格式）。

        【核心要求】
        1. 必须判断新闻的【所属区域】：
           - 如果是发生在中国、或涉及中国公司的 AI 新闻，category 填 "国内"。
           - 否则（如 OpenAI, Google, 美国初创公司等），category 填 "国外"。
        2. 保留原文 Link。
        3. 输出纯 JSON 列表，无 Markdown。

        JSON 格式示例：
        [
            {{
                "category": "国内",  <-- 必须严格从 ["国内", "国外"] 中二选一
                "tag": "大模型",
                "title": "中文标题",
                "link": "https://...",
                "summary": "中文摘要",
                "comment": "毒舌点评"
            }}
        ]

        新闻内容：
        {text_content}
        """
        
        time.sleep(2) 
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ API 错误: {e}")
        return []

if __name__ == "__main__":
    today_date, today_week = get_current_date_info()
    history_file = 'news.json'
    
    archive_data = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, dict) and not "news" in content: archive_data = content
        except: pass

    # 生成今日新闻
    print(f"📅 生成 {today_date} ({today_week})...")
    today_news = summarize_with_gemini(get_latest_news())
    
    if today_news:
        archive_data[today_date] = {
            "week": today_week,
            "articles": today_news
        }
    
    # 7天滚动清洗
    sorted_dates = sorted(archive_data.keys(), reverse=True)
    final_data = {d: archive_data[d] for d in sorted_dates[:7]}
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 完成！")
