#!/usr/bin/env python3
"""
GitHub Actions 触发器
用于手动触发 my-ai-news 的 Daily AI News Update workflow
"""

import os
import sys
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "damei1512"
REPO_NAME = "my-ai-news"
WORKFLOW_ID = "daily_update.yml"

def trigger_workflow():
    """触发 GitHub Actions Workflow"""
    if not GITHUB_TOKEN:
        print("❌ 错误：GITHUB_TOKEN 未配置")
        return False
    
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_ID}/dispatches"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    data = {
        "ref": "main"  # 触发 main 分支
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 204:
            print("✅ 成功触发 Workflow！")
            print(f"📎 查看状态: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions")
            return True
        elif response.status_code == 401:
            print("❌ 认证失败：Token 无效或权限不足")
            return False
        elif response.status_code == 404:
            print("❌ 找不到 Workflow 或仓库")
            return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def check_workflow_status():
    """检查最近的 workflow 运行状态"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs?per_page=5"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            runs = response.json().get("workflow_runs", [])
            print("\n📊 最近5次运行:")
            for run in runs[:5]:
                status = "✅" if run["conclusion"] == "success" else "❌" if run["conclusion"] == "failure" else "⏳"
                print(f"  {status} {run['name']} - {run['created_at'][:10]} ({run['status']})")
            return True
        else:
            print(f"❌ 获取状态失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查状态异常: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_workflow_status()
    else:
        print("🚀 正在触发 AI News Update...")
        if trigger_workflow():
            print("\n⏳ Workflow 已启动，大约需要 2-3 分钟完成")
            print("💡 提示: 运行 'python trigger_workflow.py status' 查看最近状态")
