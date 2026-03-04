"""
X (Twitter) 抓取模块
通过 RSSHub 订阅 X 账号 RSS
"""

import feedparser
import yaml
import time
from datetime import datetime, timedelta
import pytz

def load_x_sources():
    """加载 X 账号配置"""
    with open('x_sources.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('X_SOURCES', {}), config.get('RSS_HUB_NODES', [])

def fetch_x_user_tweets(username, name, category, rss_nodes):
    """抓取单个 X 用户的最新推文"""
    tweets = []
    
    for node in rss_nodes:
        try:
            rss_url = f"{node}/x/user/{username}"
            print(f"   尝试: {rss_url}")
            
            feed = feedparser.parse(rss_url)
            
            if feed.entries:
                print(f"   ✓ [{category}] {name} (@{username}) - {len(feed.entries)} 条推文")
                
                # 只取最近24小时的推文
                beijing_tz = pytz.timezone('Asia/Shanghai')
                now = datetime.now(beijing_tz)
                yesterday = now - timedelta(hours=24)
                
                for entry in feed.entries[:5]:  # 最多5条
                    # 解析发布时间
                    pub_time = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC)
                        pub_time = pub_time.astimezone(beijing_tz)
                    
                    # 只保留24小时内的推文
                    if pub_time and pub_time < yesterday:
                        continue
                    
                    # 清理推文内容
                    content = entry.get('title', entry.get('summary', ''))
                    # 移除多余空格和链接
                    content = ' '.join(content.split())
                    
                    if len(content) > 10:  # 过滤太短的
                        tweets.append({
                            "category": category,
                            "tag": "X动态",
                            "title": f"【{name}】{content[:60]}{'...' if len(content) > 60 else ''}",
                            "summary": content,
                            "link": entry.link,
                            "source_name": f"@{username}",
                            "pub_time": pub_time.strftime("%m-%d %H:%M") if pub_time else ""
                        })
                
                return tweets  # 成功获取后退出
                
        except Exception as e:
            print(f"   ❌ {node} 失败: {str(e)[:50]}")
            continue
    
    print(f"   ⚠️ 未获取到 @{username} 的内容")
    return []

def fetch_all_x_tweets():
    """抓取所有配置的 X 用户推文"""
    x_sources, rss_nodes = load_x_sources()
    all_tweets = []
    
    print("🐦 开始抓取 X (Twitter) 大V...")
    
    for category, users in x_sources.items():
        for user in users:
            tweets = fetch_x_user_tweets(
                user['username'], 
                user['name'], 
                user['category'],
                rss_nodes
            )
            all_tweets.extend(tweets)
            time.sleep(0.5)  # 避免请求过快
    
    # 去重（基于链接）
    seen_links = set()
    unique_tweets = []
    for tweet in all_tweets:
        if tweet['link'] not in seen_links:
            seen_links.add(tweet['link'])
            unique_tweets.append(tweet)
    
    print(f"\n📊 X抓取完成: 共 {len(unique_tweets)} 条推文（去重后）")
    return unique_tweets

if __name__ == "__main__":
    # 测试运行
    tweets = fetch_all_x_tweets()
    for t in tweets[:3]:
        print(f"\n{t['title']}")
        print(f"  {t['summary'][:100]}...")
