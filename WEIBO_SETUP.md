# 微博大V RSS 配置说明

## 已配置的大V列表

| 姓名 | 分类 | 标签 | UID |
|------|------|------|-----|
| 雷军 | 数码 | 小米、手机、汽车 | 1749127163 |
| 闫俊杰 | AI | MiniMax、大模型 | 1722568544 |
| 杨植麟 | AI | 月之暗面、Kimi | 2649334664 |
| 罗永浩 | 科技 | 锤子、直播、创业 | 1640296591 |
| 李想 | 科技 | 理想汽车、新能源 | 1647574422 |

## 部署步骤

### 1. 安装依赖
```bash
cd ~/my-ai-news
pip3 install pyyaml requests
```

### 2. 运行测试
```bash
# 测试微博抓取
python3 weibo_fetcher.py
```

### 3. 生成完整日报
```bash
# 设置 Gemini API Key
export GEMINI_API_KEY="your-api-key"

# 运行主脚本
python3 auto_gen.py
```

## 添加/删除大V

编辑 `weibo_sources.yaml`：

```yaml
weibo_sources:
  - name: "新大V名字"
    uid: "微博UID"
    category: "分类"
    tags: ["标签1", "标签2"]
    enabled: true  # false 表示禁用
```

获取微博UID方法：
1. 打开微博用户主页
2. 查看页面源码，搜索 `oid`
3. 或者使用在线工具：https://weibo.iiilab.com/

## 技术说明

微博抓取使用 RSSHub 的公开镜像：
- https://rsshub.app/weibo/user/{uid}
- https://rsshub.rssforever.com/weibo/user/{uid}

如果抓取失败，可能是：
1. 微博设置了隐私
2. RSSHub 镜像暂时不可用
3. 微博反爬限制

解决方案：
- 等待后重试
- 自建 RSSHub（需要 Docker）
