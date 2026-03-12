import os
import json
import datetime
import feedparser
from openai import OpenAI
import time
import pytz
import re
import hashlib
from urllib.parse import urlparse
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ================= 配置区 =================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("❌ API Key 未配置")

# DeepSeek 客户端
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)
MODEL_NAME = 'deepseek-chat'

# ================= RSS 源配置（3大分类）====================
RSS_SOURCES = {
    "科技&数码": [
        # 国内科技媒体
        "https://36kr.com/feed",
        "https://www.ifanr.com/feed",
        "https://www.pingwest.com/feed",
        "https://www.jiqizhixin.com/rss",
        # 国际科技媒体
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "https://www.engadget.com/rss.xml",
        # AI公司官方
        "https://openai.com/index/rss.xml",
        "https://www.anthropic.com/rss.xml",
        # AI开发者社区
        "https://blog.langchain.dev/rss/",
        "https://news.ycombinator.com/rss",
        "https://www.lesswrong.com/rss",
        "https://www.reddit.com/r/LocalLLaMA/.rss",
        # AI Agent框架
        "https://github.com/microsoft/autogen/releases.atom",
        "https://github.com/Significant-Gravitas/AutoGPT/releases.atom",
        "https://github.com/joaomdmoura/crewAI/releases.atom",
        "https://blog.coze.com/rss",
    ],
    "游戏+影视": [
        "https://www.ign.com/rss/articles/feed",
        "https://www.gamespot.com/feeds/news/",
        "https://www.gcores.com/rss",
        "https://www.engadget.com/rss.xml",  # 含游戏数码
    ],
    "时事&热点": [
        # 国际时事
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.reutersagency.com/feed/?taxonomy=markets&post_type=reuters-best",
        # 国内热榜
        "https://rsshub.rssforever.com/jike/topic/hot",
        "https://rsshub.pseudoyu.com/jike/topic/hot",
    ]
}

# ================= 关键词白名单（3大分类）====================
KEYWORD_WHITELIST = {
    "科技&数码": [
        # 科技大公司
        "苹果", "谷歌", "微软", "英伟达", "华为", "小米", "特斯拉", "SpaceX", "OpenAI", "Anthropic", "Meta", "Google", "DeepSeek",
        # AI/大模型
        "AI", "人工智能", "大模型", "LLM", "ChatGPT", "Claude", "Gemini", "Llama", "生成式AI", "AIGC", "AGI", "多模态",
        # AI Agent
        "Agent", "智能体", "AutoGPT", "LangChain", "AutoGen", "CrewAI", "Dify", "Coze", "Manus", "Operator", "RAG", "MCP",
        # 硬科技
        "芯片", "半导体", "算力", "GPU", "机器人", "具身智能", "自动驾驶", "无人机",
        # 数码产品
        "手机", "iPhone", "Android", "相机", "笔记本", "平板", "手表", "耳机", "显示器", "屏幕", "充电", "配件",
        # 行业动态
        "融资", "IPO", "收购", "上市", "发布会", "新品", "评测", "体验",
    ],
    "游戏+影视": [
        # 游戏平台
        "Switch", "PlayStation", "Xbox", "Steam", "手游", "网游", "单机",
        # 游戏公司/作品
        "任天堂", "索尼", "微软", "原神", "王者荣耀", "黑神话", "GTA", "塞尔达", "马里奥", "宝可梦", "LOL", "Dota", "CS",
        # 游戏动态
        "发售", "销量", "更新", "DLC", "预告", "演示", "电竞", "比赛", "版本",
        # 影视
        "电影", "剧集", "Netflix", "流媒体", "预告片", "票房", "导演", "演员",
    ],
    "时事&热点": [
        # 国际
        "中美", "欧盟", "俄罗斯", "乌克兰", "美国", "中国", "日本", "韩国",
        # 经济
        "经济", "股市", "贸易", "关税", "制裁", "通胀", "GDP", "就业", "央行", "降息", "加息",
        # 政治
        "政策", "选举", "拜登", "特朗普", "马克龙", "德国", "英国",
        # 社会/热点
        "战争", "冲突", "疫情", "气候变化", "灾难", "事故", "热点", "热议", "热搜",
    ]
}

# ================= 去重管理器 =================
class ArticleDeduplicator:
    """文章去重管理器 - 支持链接去重和内容相似度去重"""
    
    def __init__(self):
        self.seen_links = set()  # 已见过的链接
        self.seen_hashes = set()  # 已见过的内容指纹
        self.removed_count = 0
    
    def normalize_link(self, link):
        """标准化链接，去除跟踪参数"""
        try:
            parsed = urlparse(link)
            # 去除常见的跟踪参数
            clean_link = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return clean_link.rstrip('/')
        except:
            return link
    
    def content_fingerprint(self, title, summary):
        """生成内容指纹用于相似度检测"""
        # 提取关键词（去除停用词后的核心词）
        text = (title + ' ' + summary).lower()
        # 去除常见停用词和标点
        text = re.sub(r'[，。？！.,?!;:"\'\s\d]+', ' ', text)
        # 提取2-3个字符的词组作为特征
        words = [w for w in text.split() if len(w) >= 2]
        # 取前10个关键词排序后生成指纹
        keywords = sorted(words)[:10]
        fingerprint = hashlib.md5(' '.join(keywords).encode()).hexdigest()[:16]
        return fingerprint
    
    def is_duplicate(self, article):
        """检查文章是否重复"""
        link = article.get('link', '')
        title = article.get('title', '')
        summary = article.get('summary', '')
        
        # 1. 链接去重
        normalized = self.normalize_link(link)
        if normalized in self.seen_links:
            return True, "链接重复"
        
        # 2. 标题相似度去重（标题完全相同或高度相似）
        normalized_title = re.sub(r'[^\w\u4e00-\u9fa5]', '', title.lower())
        for seen_link in self.seen_links:
            # 这里简化处理，实际可以维护标题索引
            pass
        
        # 3. 内容指纹去重
        fingerprint = self.content_fingerprint(title, summary)
        if fingerprint in self.seen_hashes:
            return True, "内容相似"
        
        # 记录为新文章
        self.seen_links.add(normalized)
        self.seen_hashes.add(fingerprint)
        return False, None
    
    def deduplicate_list(self, articles):
        """对文章列表进行去重"""
        unique_articles = []
        duplicates = []
        
        for article in articles:
            is_dup, reason = self.is_duplicate(article)
            if is_dup:
                duplicates.append({
                    'title': article.get('title', '')[:50],
                    'reason': reason
                })
            else:
                unique_articles.append(article)
        
        self.removed_count = len(duplicates)
        if duplicates:
            print(f"   🧹 去重: 移除 {len(duplicates)} 条重复")
            for d in duplicates[:3]:  # 只显示前3个
                print(f"      - {d['title'][:40]}... ({d['reason']})")
            if len(duplicates) > 3:
                print(f"      ... 还有 {len(duplicates)-3} 条")
        
        return unique_articles

# ================= 图片提取器 =================
class ImageExtractor:
    """从RSS提取配图（原文有图才用，无图不硬配）"""
    
    @staticmethod
    def extract_from_entry(entry):
        """从RSS entry提取图片URL"""
        # 1. 尝试获取media:content
        if 'media_content' in entry:
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    return media.get('url')
        
        # 2. 尝试获取media:thumbnail
        if 'media_thumbnail' in entry and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')
        
        # 3. 尝试从summary/content中提取img标签
        content = entry.get('summary', '') + entry.get('description', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if img_match:
            return img_match.group(1)
        
        # 4. 尝试enclosure
        if 'enclosures' in entry and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    return enc.get('href')
        
        return None

# ================= 核心函数 =================

def get_current_date_info():
    """获取北京时间日期和星期"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz)
    date_str = now.strftime("%Y-%m-%d")
    week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    week_str = week_map[now.weekday()]
    return date_str, week_str

def filter_by_keywords(articles, category):
    """按关键词过滤文章（时事、游戏分类不过滤，让Gemini处理所有内容）"""
    # 时事、游戏、热榜分类跳过关键词过滤（英文源或混合内容）
    if category in ["时事", "游戏", "热榜"]:
        return articles
    
    keywords = KEYWORD_WHITELIST.get(category, [])
    if not keywords:
        return articles
    
    filtered = []
    for article in articles:
        text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
        if any(kw.lower() in text for kw in keywords):
            filtered.append(article)
    
    if len(filtered) < len(articles):
        print(f"   📝 关键词过滤: {len(articles)} → {len(filtered)} 篇")
    
    return filtered

def fetch_news_by_category(category, urls, deduplicator):
    """抓取指定分类的新闻（含图片）"""
    print(f"📡 [{category}] 正在抓取 RSS 源...")
    articles = []
    
    for url in urls:
        try:
            feed = feedparser.parse(url)
            print(f"   ✓ {url.split('/')[2]}")  # 只显示域名
            
            for entry in feed.entries[:5]:  # 每个源取前5条
                # 提取图片
                image_url = ImageExtractor.extract_from_entry(entry)
                
                article = {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get('summary', '')[:500],
                    "image": image_url,
                    "source_domain": url.split('/')[2]
                }
                articles.append(article)
                
        except Exception as e:
            print(f"   ❌ {url} - {e}")
    
    # 去重
    articles = deduplicator.deduplicate_list(articles)
    
    # 关键词过滤
    articles = filter_by_keywords(articles, category)
    
    return articles

def summarize_with_deepseek(category, articles):
    """使用 DeepSeek 对新闻进行分类总结（含图片信息）"""
    if not articles:
        return []
    
    print(f"🤖 [{category}] 正在生成摘要...")
    try:
        # 构建带图片信息的内容
        content_parts = []
        for i, a in enumerate(articles, 1):
            img_info = f"[配图: {a.get('image', '无')}]" if a.get('image') else "[无配图]"
            content_parts.append(
                f"[{i}] 标题: {a['title']}\n"
                f"链接: {a['link']}\n"
                f"{img_info}\n"
                f"简介: {a['summary'][:300]}"
            )
        
        content = "\n\n---\n\n".join(content_parts)
        
        prompt = f"""
你是一个科技主编。请将以下{category}类新闻生成为中文日报摘要（JSON格式）。

【核心要求】
1. category 字段必须填 "{category}"
2. tag 字段填写新闻的子标签（如大模型、芯片、游戏等，3-4个字）
3. 保留原文 link
4. title 字段：**必须翻译成中文标题**，保持原标题含义，50字以内
5. summary 字段：100字以内中文摘要，突出核心信息
6. comment 字段：中文毒舌点评，50字以内，要有态度
7. image 字段：保留原文中的配图URL，如果没有则留空字符串
8. 输出纯 JSON 列表，无 Markdown

【重要】如果原文是英文，title、summary、comment 必须全部翻译成中文！

JSON 格式示例：
[
    {{
        "category": "{category}",
        "tag": "大模型",
        "title": "中文标题",
        "link": "https://...",
        "summary": "中文摘要...",
        "comment": "毒舌点评...",
        "image": "https://..." 或 ""
    }}
]

新闻内容：
{content}
"""
        
        time.sleep(1)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个专业的科技新闻主编，擅长用犀利的点评总结新闻。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        text = response.choices[0].message.content.strip()
        
        # 清理 Markdown 代码块
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        result = json.loads(text)
        
        # 确保每条新闻都有image字段
        for item in result:
            if 'image' not in item:
                item['image'] = ""
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        # 过滤掉可能包含API key的错误信息
        if "API key" in error_msg.lower() or "key" in error_msg.lower():
            print(f"❌ [{category}] API 错误: 认证失败，请检查API Key是否有效")
        else:
            print(f"❌ [{category}] API 错误: {error_msg[:100]}")
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
    deduplicator = ArticleDeduplicator()
    
    # ========== 1. 抓取 RSS 源 ==========
    print("=" * 50)
    print("📡 阶段1: 抓取 RSS 源")
    print("=" * 50)
    
    for category, urls in RSS_SOURCES.items():
        raw_news = fetch_news_by_category(category, urls, deduplicator)
        if raw_news:
            summarized = summarize_with_deepseek(category, raw_news)
            all_articles.extend(summarized)
        time.sleep(1)
    
    # ========== 2. 最终去重（跨分类）==========
    print("\n" + "=" * 50)
    print("🧹 阶段2: 跨分类去重")
    print("=" * 50)
    
    final_deduplicator = ArticleDeduplicator()
    all_articles = final_deduplicator.deduplicate_list(all_articles)
    
    # ========== 3. 配图统计 ==========
    print("\n" + "=" * 50)
    print("🖼️ 阶段3: 配图统计")
    print("=" * 50)
    
    with_image = sum(1 for a in all_articles if a.get('image'))
    print(f"   原文配图: {with_image}/{len(all_articles)} 条")
    
    # ========== 4. 抓取 X (Twitter) 大V ==========
    print("\n" + "=" * 50)
    print("🐦 阶段4: 抓取 X (Twitter) 大V")
    print("=" * 50)
    
    try:
        from x_fetcher import fetch_all_x_tweets
        x_articles = fetch_all_x_tweets()
        if x_articles:
            print(f"\n🤖 正在处理 {len(x_articles)} 条 X 推文...")
            for article in x_articles:
                article['comment'] = f"【{article.get('source_name', 'X')} 最新动态】"
            all_articles.extend(x_articles)
    except Exception as e:
        print(f"⚠️ X 抓取失败: {e}")
    
    # ========== 5. 保存数据 ==========
    print("\n" + "=" * 50)
    print("💾 阶段5: 保存数据")
    print("=" * 50)
    
    if all_articles:
        archive_data[today_date] = {
            "week": today_week,
            "articles": all_articles
        }
        print(f"✅ 今日共 {len(all_articles)} 条新闻（已去重）")
        
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
    print(f"🧹 总计去重: {deduplicator.removed_count + final_deduplicator.removed_count} 条")
