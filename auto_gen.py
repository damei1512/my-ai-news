import os
import json
import datetime
import google.generativeai as genai

# 1. 获取 Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 错误：根本没读到 Key")
    exit(1)

# 2. 显示 Key 的前 8 位（帮你确认是否真的换成新的了）
# 如果网页上显示的和你新申请的不一样，说明 GitHub 没更新成功
key_mask = f"{GEMINI_API_KEY[:8]}...******"
print(f"正在使用的 Key: {key_mask}")

genai.configure(api_key=GEMINI_API_KEY)

def diagnose_system():
    report_lines = []
    report_lines.append(f"🔐 当前使用的 Key 前缀: {GEMINI_API_KEY[:8]} (请核对)")
    
    # 3. 询问 Google：这个 Key 能用哪些模型？
    report_lines.append("📋 Google 返回的可用模型列表:")
    available_models = []
    
    try:
        # 列出所有模型
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                clean_name = m.name.replace('models/', '')
                available_models.append(clean_name)
                report_lines.append(f"   ✅ {clean_name}")
        
        if not available_models:
             report_lines.append("   ⚠️ 空！Google 说这个 Key 没有任何模型权限。")
             report_lines.append("   原因猜测：可能没有在【新项目】中创建 Key，或者需要等待几分钟生效。")

    except Exception as e:
        report_lines.append(f"   ❌ 连接 Google 失败: {str(e)}")
        report_lines.append("   原因猜测：网络问题或 Key 无效。")

    return "\n".join(report_lines)

if __name__ == "__main__":
    diagnosis = diagnose_system()
    
    # 生成报告到网页
    output = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": [{
            "tag": "系统体检",
            "title": "API 诊断报告",
            "summary": "请查看下方的详细检测结果 👇",
            "comment": diagnosis 
        }]
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
