# -*- coding: utf-8 -*-
"""修复：使用单行字符串"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 找到函数开始位置
func_start = None
for i in range(len(lines)):
    if 'api_ai_optimize_prompt' in lines[i]:
        func_start = i
        break

if func_start:
    func_end = len(lines)
    for i in range(func_start + 1, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith('@app.') or stripped.startswith('def ')) and not lines[i][0].isspace():
            func_end = i
            break
    
    # 使用单行字符串，不用三引号
    new_func_lines = [
        '@app.route(\'/api/ai/optimize-prompt\', methods=[\'POST\'])\n',
        'def api_ai_optimize_prompt():\n',
        '    """AI optimize prompt template"""\n',
        '    from flask import request, jsonify\n',
        '\n',
        '    try:\n',
        '        data = request.get_json(silent=True) or {}\n',
        '        user_input = data.get(\'user_input\') or \'\'\n',
        '        brand = data.get(\'brand\') or \'\'\n',
        '        kb_content = data.get(\'kb_content\') or \'\'\n',
        '        topic = data.get(\'topic\') or \'\'\n',
        '        user_instruction = data.get(\'user_instruction\') or \'\'\n',
        '        word_min = data.get(\'word_min\') or 500\n',
        '        word_max = data.get(\'word_max\') or 2000\n',
        '\n',
        '        if not user_input.strip():\n',
        '            return jsonify({\'ok\': False, \'error\': \'Please input content\'}), 400\n',
        '\n',
        '        from llm_qwen import call_qwen\n',
        '\n',
        '        settings = db.get_all_settings()\n',
        '\n',
        '        if not settings.get(\'qwen_api_key\'):\n',
        '            return jsonify({\'ok\': False, \'error\': \'AI service not configured\'}), 400\n',
        '\n',
        '        system_prompt = "You are a Prompt Engineering expert. Convert user writing requirements into a structured Prompt template with variable placeholders. Required variables: {brand}, {kb_content}, {topic}, {user_instruction}, {word_min}, {word_max}. Output only the optimized template."\n',
        '\n',
        '        user_msg = "Convert this to Prompt template: " + user_input + ". Use variables: brand, kb_content, topic, user_instruction, word_min, word_max"\n',
        '\n',
        '        result = call_qwen(\n',
        '            settings,\n',
        '            user_prompt=user_msg,\n',
        '            system_prompt=system_prompt,\n',
        '            max_tokens=2000,\n',
        '            temperature=0.7,\n',
        '        )\n',
        '\n',
        '        optimized = result.strip() if result else None\n',
        '        if not optimized:\n',
        '            return jsonify({\'ok\': False, \'error\': \'AI returned empty\'}), 500\n',
        '\n',
        '        missing_vars = []\n',
        '        for var in [\'{brand}\', \'{kb_content}\', \'{topic}\', \'{user_instruction}\', \'{word_min}\', \'{word_max}\']:\n',
        '            if var not in optimized:\n',
        '                missing_vars.append(var)\n',
        '\n',
        '        return jsonify({\n',
        '            \'ok\': True,\n',
        '            \'optimized\': optimized,\n',
        '            \'missing_vars\': missing_vars if missing_vars else None\n',
        '        })\n',
        '\n',
        '    except Exception as e:\n',
        '        print(f"[AI Optimize] Error: {str(e)}")\n',
        '        return jsonify({\'ok\': False, \'error\': f\'Failed: {str(e)}\'}), 500\n',
        '\n',
        '\n',
    ]
    
    lines[func_start:func_end] = new_func_lines
    
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
