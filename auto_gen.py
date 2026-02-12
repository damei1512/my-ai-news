import os
import json
import datetime
import feedparser
import google.generativeai as genai
import time

# ================= 配置区 =================
# 1. 验证 Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ API Key 未配置")

genai.configure(api_key=GEMINI_API_KEY)
# 继续使用你验证过可用的 Flash 模型（省钱且快）
MODEL_NAME = 'gemini-flash-latest'

# ================= 核心逻辑 =================

def get_current_date_info():
    """获取当前日期和星期几（中文）"""
    now = datetime.datetime.now()
    # 修正时区：GitHub Actions 默认是 UTC，我们需要 +8 小时变成北京时间
    beijing_time = now + datetime.timedelta(hours=8)
    date_str = beijing_time.strftime("%Y-%m-%d")
    
    week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    week_str = week_map[beijing_time.weekday()]
    
    return date_str, week_str

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
            print(f"   - 连接 {url} 成功")
            for entry in feed.entries[:2]:
                # 拼接链接，确保 AI 能读取到
                articles.append(f"标题: {entry.title}\n链接: {entry.link}\n简介: {entry.summary[:200]}")
        except Exception as e:
            print(f"   ❌ 连接 {url} 失败: {e}")

    if not articles:
        print("⚠️ 未抓取到新闻，生成占位数据")
        return "Title: No News Today\nLink: #\nSummary: System is running but no RSS updates found."
    
    return "\n\n---\n\n".join(articles)

def summarize_with_gemini(text_content):
    print(f"🤖 正在呼叫 {MODEL_NAME}...")
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        prompt = f"""
        你是一个科技主编。请将以下英文新闻生成为中文日报摘要（JSON格式）。
        
        【严格要求】
        1. 输出必须是纯 JSON 列表，不要 Markdown 标记。
        2. 保留原文 Link。
        
        格式示例：
        [
            {{
                "tag": "AI大事件",
                "title": "中文标题",
                "link": "https://...",
                "summary": "中文摘要",
                "comment": "一句话毒舌点评"
            }}
        ]

        新闻内容：
        {text_content}
        """
        
        time.sleep(2) # 防并发限制
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 强力清洗格式
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"❌ API 错误: {e}")
        return []

if __name__ == "__main__":
    # 1. 准备基础数据
    today_date, today_week = get_current_date_info()
    history_file = 'news.json'
    
    # 2. 读取旧档案 (带容错处理)
    archive_data = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                # 检查格式是否为新版字典格式，如果不是则丢弃旧数据
                if isinstance(content, dict) and not "news" in content: 
                    archive_data = content
                else:
                    print("⚠️ 旧数据格式不兼容，已重置档案库")
        except:
            print("⚠️ 读取档案失败，重置档案库")

    # 3. 生成今日新闻
    print(f"📅 正在生成 {today_date} ({today_week}) 的日报...")
    today_news = summarize_with_gemini(get_latest_news())
    
    if today_news:
        archive_data[today_date] = {
            "week": today_week,
            "articles": today_news
        }
    
    # 4. 执行“7天滚动清洗”策略
    # 按日期倒序排列
    sorted_dates = sorted(archive_data.keys(), reverse=True)
    # 只保留前7个
    keep_dates = sorted_dates[:7]
    final_data = {d: archive_data[d] for d in keep_dates}
    
    # 5. 保存
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 存档完成！当前保留日期: {keep_dates}")
