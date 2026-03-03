#!/usr/bin/env python3
"""增量更新脚本 - 只更新热榜和时事（午间/晚间）"""
import os
import json
import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

print(f"\n{'='*50}")
print(f"🔄 增量更新 - {datetime.datetime.now().strftime('%H:%M')}")
print(f"{'='*50}")

# 读取现有数据
with open('news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取今天的key
today = list(data.keys())[0]
print(f"📅 更新日期: {today}")

# 运行热榜生成
print("\n🔥 更新热榜...")
try:
    import subprocess
    result = subprocess.run(['python3', 'gen_rebang.py'], 
                          capture_output=True, text=True, timeout=120)
    print(result.stdout)
    if result.stderr:
        print(f"⚠️ {result.stderr}")
except Exception as e:
    print(f"❌ 热榜更新失败: {e}")

# 可选：运行时事生成
# print("\n📰 更新时事...")
# try:
#     result = subprocess.run(['python3', 'gen_shishi.py'], 
#                           capture_output=True, text=True, timeout=120)
#     print(result.stdout)
# except Exception as e:
#     print(f"❌ 时事更新失败: {e}")

# 读取更新后的数据
with open('news.json', 'r', encoding='utf-8') as f:
    new_data = json.load(f)

new_count = len(new_data[today]['articles'])
old_count = len(data[today]['articles'])
added = new_count - old_count

print(f"\n{'='*50}")
print(f"✅ 增量更新完成")
print(f"   原有: {old_count} 条")
print(f"   新增: {added} 条")
print(f"   总计: {new_count} 条")
print(f"{'='*50}\n")

# Git 提交（可选，如果配置了git）
try:
    import subprocess
    subprocess.run(['git', 'add', 'news.json'], check=False)
    subprocess.run(['git', 'commit', '-m', f'增量更新: {today} {datetime.datetime.now().strftime("%H:%M")}'], check=False)
    subprocess.run(['git', 'push'], check=False)
    print("🚀 已推送到 GitHub")
except:
    pass
