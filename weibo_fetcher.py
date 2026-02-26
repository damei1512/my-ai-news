#!/usr/bin/env python3
"""
微博大V内容抓取模块
使用 RSSHub 格式生成微博 RSS
"""

import json
import yaml
import requests
import re
from datetime import datetime

# 加载配置
with open('weibo_sources.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

WEIBO_SOURCES = config.get('weibo_sources', [])

def fetch_weibo_rss(uid, name):
    """
    抓取微博 RSS
    使用 RSSHub 的 weibo/user/{uid} 接口
    """
    # 尝试多个 RSSHub 镜像
    rsshub_mirrors = [
        "https://rsshub.app",  # 官方（可能慢）
        "https://rsshub.rssforever.com",
        "https://rsshub.pseudoyu.com",
        "http://localhost:1200",  # 本地（如果部署了）
    ]
    
    for mirror in rsshub_mirrors:
        try:
            url = f"{mirror}/weibo/user/{uid}"
            print(f"   尝试: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return parse_weibo_rss(response.text, name)
        except Exception as e:
            print(f"   ❌ {mirror} 失败: {e}")
            continue
    
    return []

def parse_weibo_rss(rss_content, source_name):
    """解析微博 RSS XML"""
    import xml.etree.ElementTree as ET
    
    try:
        root = ET.fromstring(rss_content)
        items = []
        
        # 提取 item
        for item in root.findall('.//item'):
            title = item.find('title')
            link = item.find('link')
            description = item.find('description')
            pubDate = item.find('pubDate')
            
            if title is not None and link is not None:
                # 清理 HTML 标签
                summary = re.sub(r'<[^>]+>', '', description.text if description is not None else '')
                items.append({
                    'title': title.text[:100] if title.text else '无标题',
                    'link': link.text,
                    'summary': summary[:300] if summary else '',
                    'source_name': source_name,
                    'pub_date': pubDate.text if pubDate is not None else datetime.now().isoformat()
                })
        
        return items
    except Exception as e:
        print(f"   ❌ 解析失败: {e}")
        return []

def fetch_all_weibo():
    """抓取所有配置的微博大V"""
    all_articles = []
    
    print("📱 开始抓取微博大V...")
    
    for source in WEIBO_SOURCES:
        if not source.get('enabled', True):
            continue
            
        name = source['name']
        uid = source['uid']
        category = source.get('category', '科技')
        
        print(f"\n🔍 [{category}] {name} ({uid})")
        
        articles = fetch_weibo_rss(uid, name)
        
        if articles:
            print(f"   ✅ 获取 {len(articles)} 条")
            # 添加分类信息
            for article in articles:
                article['category'] = category
                article['tag'] = source.get('tags', ['微博'])[0]
            all_articles.extend(articles[:5])  # 每人取前5条
        else:
            print(f"   ⚠️ 未获取到内容")
    
    print(f"\n📊 微博抓取完成: 共 {len(all_articles)} 条")
    return all_articles

if __name__ == "__main__":
    articles = fetch_all_weibo()
    for a in articles[:3]:
        print(f"\n- {a['source_name']}: {a['title'][:50]}...")
