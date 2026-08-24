# -*- coding: utf-8 -*-
"""用英文提示词修复"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 找到函数开始位置
func_start = None
for i in range(len(lines)):
    if 'api_ai_optimize_prompt' in lines[i]:
        func_start = i
        print(f"找到函数定义在第{i+1}行")
        break

if func_start:
    # 找到函数结束位置
    func_end = len(lines)
    for i in range(func_start + 1, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith('@app.') or stripped.startswith('def ')) and not lines[i][0].isspace():
            func_end = i
            break
    
    print(f"替换第{func_start+1}行到第{func_end}行")
    
    # 新的完整函数代码（使用英文提示词避免编码问题）
    new_func = '''@app.route('/api/ai/optimize-prompt', methods=['POST'])
def api_ai_optimize_prompt():
    """AI optimize prompt template"""
    from flask import request, jsonify

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
            return jsonify({'ok': False, 'error': 'Please input content'}), 400

        try:
            from llm_qwen import call_qwen
        except ImportError:
            return jsonify({'ok': False, 'error': 'LLM module not found'}), 500

        settings = db.get_all_settings()
        
        if not settings.get('qwen_api_key'):
            return jsonify({
                'ok': False,
                'error': 'AI service not configured'
            }), 400

        system_prompt = """You are a Prompt Engineering expert. Convert user writing requirements into a structured Prompt template with variable placeholders.

**Core Requirements:**
1. Analyze user input and identify parts that can use variables
2. Replace specific content (brand name, topic, word count) with variable placeholders
3. Add missing variables naturally if user did not mention them
4. Output should be professional, clear, and well-structured

**Required Variables (must all be used):**
- {brand} - Brand/Company/Product name
- {kb_content} - Knowledge base reference material
- {topic} - Writing topic/keywords
- {user_instruction} - Additional user requirements
- {word_min} - Minimum word count
- {word_max} - Maximum word count

**Output Rules:**
- Output ONLY the optimized Prompt template text
- Use markdown format for clarity"""

        user_msg = f"""Convert this writing requirement into a professional Prompt template with variables:

---
{user_input}
---

Replace: Brand->{brand}, Reference->{kb_content}, Topic->{topic}, Extra reqs->{user_instruction}, Min words->{word_min}, Max words->{word_max}"""

        result = call_qwen(
            settings,
            user_prompt=user_msg,
            system_prompt=system_prompt,
            max_tokens=2000,
            temperature=0.7,
        )

        optimized = result.strip() if result else None
        if not optimized:
            return jsonify({'ok': False, 'error': 'AI returned empty'}), 500

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
        print(f"[AI Optimize] Error: {str(e)}")
        return jsonify({'ok': False, 'error': f'Failed: {str(e)}'}), 500


'''
    
    lines[func_start:func_end] = [new_func]
    
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)

# 验证语法
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n" + "="*50)
    print("SUCCESS! app.py syntax is correct!")
    print("="*50)
except SyntaxError as e:
    print(f"\nERROR Line {e.lineno}: {e.msg}")
    content_lines = content.split('\n')
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
