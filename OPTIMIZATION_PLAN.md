# AI 资讯聚合 - 质量与效率优化方案

## 🎯 当前问题诊断

### 质量问题
1. **RSS 源噪音大** - 抓取到不相关内容
2. **分类不准确** - AI 误判新闻类别
3. **摘要质量参差** - 有些摘要太水
4. **重复内容** - 不同源报道同一事件

### 效率问题
1. **全量抓取** - 每次重新抓所有历史
2. **API 调用频繁** - 每个分类单独请求
3. **串行处理** - 一个源失败影响整体
4. **无缓存机制** - 重复消耗 token

---

## 🚀 优化方案

### 阶段1：内容质量提升（立即做）

#### 1.1 关键词白名单过滤
```python
# 在抓取阶段过滤无关内容
KEYWORD_WHITELIST = {
    "科技": ["芯片", "半导体", "融资", "IPO", "收购", "苹果", "谷歌", "微软"],
    "数码": ["手机", "相机", "笔记本", "发布会", "评测", "新品"],
    "游戏": ["Switch", "PlayStation", "Steam", "手游", "网游", "DLC"],
    "AI": ["大模型", "ChatGPT", "Claude", "算力", "Agent", "多模态"]
}

# 只保留包含关键词的文章
def filter_by_keywords(articles, category):
    keywords = KEYWORD_WHITELIST.get(category, [])
    return [a for a in articles if any(k in a['title']+a['summary'] for k in keywords)]
```

#### 1.2 提示词优化（Few-shot 示例）
```python
prompt = """
你是一个资深科技主编，请将以下新闻分类总结。

【分类标准】
- 科技：硬件、芯片、半导体、企业融资并购
- 数码：消费电子、手机、相机、评测
- 游戏：主机、PC游戏、手游、电竞
- 时事：政治、经济、社会热点（非科技）
- AI：人工智能、大模型、机器学习、自动驾驶

【示例】
输入: "苹果发布新款iPhone"
输出: {{"category": "数码", "tag": "手机", "confidence": 0.95}}

输入: "OpenAI发布GPT-5"
输出: {{"category": "AI", "tag": "大模型", "confidence": 0.98}}

【质量要求】
1. 摘要必须包含：谁 + 做了什么 + 影响
2. 点评要有态度，避免泛泛而谈
3. 置信度<0.7的文章直接丢弃

新闻内容：{content}
"""
```

#### 1.3 去重机制
```python
from difflib import SequenceMatcher

def is_duplicate(new_article, existing_articles, threshold=0.7):
    """基于标题相似度去重"""
    for existing in existing_articles:
        similarity = SequenceMatcher(None, 
            new_article['title'], 
            existing['title']
        ).ratio()
        if similarity > threshold:
            return True
    return False
```

---

### 阶段2：效率优化（本周做）

#### 2.1 增量更新机制
```python
import hashlib

def get_article_id(article):
    """生成文章唯一ID"""
    return hashlib.md5(article['link'].encode()).hexdigest()

# 记录已处理的文章ID
PROCESSED_IDS_FILE = 'processed_ids.json'

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE) as f:
            return set(json.load(f))
    return set()

def save_processed_ids(ids):
    with open(PROCESSED_IDS_FILE, 'w') as f:
        json.dump(list(ids), f)

# 只处理新文章
processed_ids = load_processed_ids()
new_articles = [a for a in all_articles 
                if get_article_id(a) not in processed_ids]
```

#### 2.2 并发抓取
```python
import asyncio
import aiohttp

async def fetch_rss(session, url):
    async with session.get(url) as response:
        return await response.text()

async def fetch_all_rss(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_rss(session, url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

#### 2.3 批量 API 调用
```python
# 现在的做法：每个分类调一次API（5次调用）
# 优化后：所有文章一次调用，让AI自己分类

def summarize_batch(all_articles):
    """批量处理所有文章"""
    content = "\n\n---\n\n".join([
        f"[{i}] {a['title']}\n{a['summary'][:200]}"
        for i, a in enumerate(all_articles)
    ])
    
    prompt = f"""
    请将以下{len(all_articles)}条新闻分类总结。
    输出JSON数组，每个元素包含：index, category, tag, title, summary, comment
    
    新闻列表：
    {content}
    """
    
    # 一次API调用处理所有文章
    response = model.generate_content(prompt)
    return json.loads(response.text)
```

#### 2.4 RSS 源健康度监控
```python
SOURCE_HEALTH = {}

def record_source_result(source, success, article_count=0):
    """记录源的健康状况"""
    if source not in SOURCE_HEALTH:
        SOURCE_HEALTH[source] = {"success": 0, "fail": 0, "last_articles": 0}
    
    if success:
        SOURCE_HEALTH[source]["success"] += 1
        SOURCE_HEALTH[source]["last_articles"] = article_count
    else:
        SOURCE_HEALTH[source]["fail"] += 1
    
    # 连续失败3次，降低优先级
    if SOURCE_HEALTH[source]["fail"] >= 3:
        print(f"⚠️ {source} 连续失败，降低抓取频率")

def should_fetch_source(source):
    """决定是否抓取该源"""
    health = SOURCE_HEALTH.get(source, {})
    fail_count = health.get("fail", 0)
    
    # 指数退避：失败越多，跳过概率越高
    import random
    if random.random() < (fail_count * 0.3):
        return False
    return True
```

---

### 阶段3：高级功能（长期）

#### 3.1 用户反馈闭环
```javascript
// 前端添加反馈按钮
<div class="feedback">
  <span>这篇文章分类对吗？</span>
  <button onclick="feedback('${item.id}', 'correct')">✓</button>
  <button onclick="feedback('${item.id}', 'wrong')">✗</button>
</div>

// 后端收集反馈，用于优化AI提示词
```

#### 3.2 热点加权排序
```python
def calculate_hot_score(article):
    """计算热度分数"""
    score = 0
    
    # 关键词热度
    hot_keywords = ["OpenAI", "苹果", "英伟达", "融资", "发布会"]
    for kw in hot_keywords:
        if kw in article['title']:
            score += 10
    
    # 时效性（越新分越高）
    # 多源报道（同一事件被多个源报道）
    
    return score

# 按热度排序
articles.sort(key=calculate_hot_score, reverse=True)
```

#### 3.3 个性化推荐
```python
# 记录用户点击行为
USER_PREFERENCES = {}

def record_click(user_id, article_category):
    """记录用户偏好"""
    if user_id not in USER_PREFERENCES:
        USER_PREFERENCES[user_id] = {}
    USER_PREFERENCES[user_id][article_category] = \
        USER_PREFERENCES[user_id].get(article_category, 0) + 1

def get_personalized_feed(user_id, articles):
    """个性化排序"""
    prefs = USER_PREFERENCES.get(user_id, {})
    return sorted(articles, 
                  key=lambda a: prefs.get(a['category'], 0), 
                  reverse=True)
```

---

## 📊 预期效果

| 指标 | 当前 | 优化后 |
|------|------|--------|
| 每次API调用 | 5次 | 1次 |
| 抓取时间 | 30秒 | 5秒 |
| 无关内容 | ~30% | <10% |
| Token消耗 | 高 | 降低60% |
| 重复文章 | 有 | 基本消除 |

---

## 🛠️ 下一步行动

1. **立即** - 添加关键词过滤（10分钟）
2. **今天** - 优化提示词 + 去重（30分钟）
3. **本周** - 增量更新 + 并发抓取（1小时）
4. **下周** - 用户反馈 + 热点排序（2小时）

要我帮你先实现哪个？🚀
