# -*- coding: utf-8 -*-
"""修复AI优化函数"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 找到函数开始位置
func_start = None
for i in range(len(lines)):
    if 'def optimize_prompt' in lines[i] or 'api_ai_optimize' in lines[i]:
        func_start = i
        print(f"找到函数定义在第{i+1}行: {lines[i].rstrip()}")
        break

if func_start:
    # 找到函数结束位置（下一个 @app. 或 def 在顶层）
    func_end = len(lines)
    for i in range(func_start + 1, len(lines)):
        stripped = lines[i].strip()
        # 查找顶层装饰器或函数定义（非缩进）
        if (stripped.startswith('@app.') or stripped.startswith('def ')) and not lines[i][0].isspace():
            func_end = i
            print(f"函数结束于第{i+1}行")
            break
    
    print(f"\n需要替换第{func_start+1}行到第{func_end}行")
    
    # 新的完整函数代码
    new_func = '''@app.route('/api/ai/optimize-prompt', methods=['POST'])
def api_ai_optimize_prompt():
    """AI优化指令模板"""
    from flask import request, jsonify
    import json

    try:
        data = request.get_json(silent=True) or {}
        user_input = data.get('user_input') or ''
        brand = data.get('brand') or ''
        kb_content = data.get('kb_content') or ''
        topic = data.get('topic') or ''
        user_instruction = data.get('user_instruction') or ''
        word_min = data.get('word_min') or 500
        word_max = data.get('word_max') or 2000

        if not user_input.strip():
            return jsonify({'ok': False, 'error': '请输入原始指令内容'}), 400

        try:
            from llm_qwen import call_qwen
        except ImportError:
            return jsonify({'ok': False, 'error': 'LLM模块未安装'}), 500

        settings = db.get_all_settings()
        
        if not settings.get('qwen_api_key'):
            return jsonify({
                'ok': False,
                'error': 'AI服务未配置，请先在系统设置中配置通义千问API Key'
            }), 400

        system_prompt = """你是一个专业的Prompt工程专家。你的任务是将用户输入的写作需求优化为一个结构清晰、变量完整的Prompt模板。

**核心要求：**
1. 必须智能分析用户输入的内容，识别出哪些部分可以用变量替代
2. 将用户描述中提到的具体内容（如品牌名、主题、字数要求等）替换为对应的变量占位符
3. 如果用户没有提到某些变量相关的内容，要在合适的位置自然地加入该变量
4. 输出的Prompt要专业、结构清晰、易于理解

**必须包含的变量（每个都必须用到）：**
- {brand} - 品牌名称（当提到"品牌"、"公司"、"产品名"时替换）
- {kb_content} - 知识库参考资料（当提到"参考内容"、"资料"、"背景信息"时替换）
- {topic} - 写作主题/关键词（当提到"主题"、"关键词"、"标题"、"关于XX"时替换）
- {user_instruction} - 用户额外要求（当提到"其他要求"、"特别注意事项"、"补充说明"时保留或添加）
- {word_min} - 最少字数（当提到"至少"、"最少"、"不少于X字"时替换）
- {word_max} - 最多字数（当提到"最多"、"不超过"、"上限X字"时替换）

**输出规则：**
- 直接输出优化后的Prompt模板文本，不要任何解释、前编或后编
- 保持中文输出
- Prompt要清晰、有条理，可以使用markdown格式"""

        user_msg = f"""请将以下写作需求优化为一个专业的Prompt模板。分析内容并将其具体信息替换为对应的变量：

---
{user_input}
---

**注意：**
- 品牌/公司名 -> {{brand}}
- 参考资料内容 -> {{kb_content}}
- 写作主题/关键词 -> {{topic}}
- 其他额外要求 -> {{user_instruction}}
- 最少字数 -> {{word_min}} 字
- 最多字数 -> {{word_max}} 字"""

        result = call_qwen(
            settings,
            user_prompt=user_msg,
            system_prompt=system_prompt,
            max_tokens=2000,
            temperature=0.7,
        )

        optimized = result.strip() if result else None
        if not optimized:
            return jsonify({'ok': False, 'error': 'AI返回为空'}), 500

        # 检查必需变量
        missing_vars = []
        for var in ['{brand}', '{kb_content}', '{topic}', '{user_instruction}', '{word_min}', '{word_max}']:
            if var not in optimized:
                missing_vars.append(var)

        return jsonify({
            'ok': True,
            'optimized': optimized,
            'missing_vars': missing_vars if missing_vars else None
        })

    except Exception as e:
        print(f"[AI优化] 错误: {str(e)}")
        return jsonify({'ok': False, 'error': f'AI优化失败: {str(e)}'}), 500


'''
    
    # 替换函数
    lines[func_start:func_end] = [new_func]
    
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)
    
    print("\n函数已替换!")

# 验证语法
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n" + "="*50)
    print("✓✓✓ 语法完全正确! app.py 修复成功! ✓✓✓")
    print("="*50)
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    content_lines = content.split('\n')
    for j in range(max(0, e.lineno-5), min(e.lineno+6, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
