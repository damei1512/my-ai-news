#!/bin/bash
# 部署脚本 - my-ai-news

echo "🚀 开始部署 my-ai-news..."

# 1. 进入项目目录
cd ~/my-ai-news

# 2. 安装 Python 依赖
echo "📦 安装依赖..."
pip3 install --user feedparser google-generativeai pytz pyyaml requests

# 3. 检查依赖
echo "🔍 检查依赖..."
python3 -c "import feedparser; import google.generativeai; import yaml; import requests; print('✅ 所有依赖已安装')"

# 4. 设置 API Key
echo ""
echo "⚠️ 请设置 Gemini API Key:"
echo "export GEMINI_API_KEY='你的API密钥'"

# 5. 测试运行
echo ""
echo "🧪 测试抓取（需要API Key）..."
echo "运行: python3 auto_gen.py"

echo ""
echo "✅ 部署完成！"
