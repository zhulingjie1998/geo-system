# -*- coding: utf-8 -*-
"""彻底重写AI优化函数 - 从第一个装饰器开始"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 找到所有 @app.route('/api/ai/optimize-prompt 的位置
route_positions = []
for i in range(len(lines)):
    if '/api/ai/optimize-prompt' in lines[i]:
        route_positions.append(i)
        print(f"找到路由定义在第{i+1}行: {lines[i].rstrip()[:80]}")

if route_positions:
    # 从第一个路由位置开始
    start = route_positions[0]
    
    # 找到函数结束（下一个顶层装饰器或函数）
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith('@app.') or stripped.startswith('def ')) and not lines[i][0].isspace():
            # 确保不是我们正在处理的函数
            if '/api/ai/optimize-prompt' not in lines[i] and 'api_ai_optimize_prompt' not in lines[i]:
                end = i
                print(f"函数结束于第{i+1}行: {lines[i].rstrip()[:60]}")
                break
    
    print(f"\n将删除第{start+1}行到第{end}行 ({end-start}行)")
    
    # 新的完整函数
    new_func_lines = [
        "@app.route('/api/ai/optimize-prompt', methods=['POST'])\n",
        "def api_ai_optimize_prompt():\n",
        "    from flask import request, jsonify\n",
        "\n",
        "    try:\n",
        "        data = request.get_json(silent=True) or {}\n",
        "        user_input = data.get('user_input') or ''\n",
        "\n",
        "        if not user_input.strip():\n",
        "            return jsonify({'ok': False, 'error': 'Please input content'}), 400\n",
        "\n",
        "        from llm_qwen import call_qwen\n",
        "\n",
        "        settings = db.get_all_settings()\n",
        "\n",
        "        if not settings.get('qwen_api_key'):\n",
        "            return jsonify({'ok': False, 'error': 'AI service not configured'}), 400\n",
        "\n",
        "        system_prompt = ('You are a Prompt Engineering expert. '\n",
        "            'Convert requirements into structured Prompt template with variables: '\n",
        "            '{brand}, {kb_content}, {topic}, {user_instruction}, {word_min}, {word_max}. '\n",
        "            'Output only the optimized template text.')\n",
        "\n",
        "        user_msg = ('Convert to Prompt template: ' + user_input + \n",
        "            '. Use variables for brand, topic, word count, etc.')\n",
        "\n",
        "        result = call_qwen(\n",
        "            settings,\n",
        "            user_prompt=user_msg,\n",
        "            system_prompt=system_prompt,\n",
        "            max_tokens=2000,\n",
        "            temperature=0.7,\n",
        "        )\n",
        "\n",
        "        optimized = result.strip() if result else None\n",
        "        if not optimized:\n",
        "            return jsonify({'ok': False, 'error': 'AI returned empty'}), 500\n",
        "\n",
        "        missing_vars = []\n",
        "        for var in ['{brand}', '{kb_content}', '{topic}', '{user_instruction}', '{word_min}', '{word_max}']:\n",
        "            if var not in optimized:\n",
        "                missing_vars.append(var)\n",
        "\n",
        "        return jsonify({\n",
        "            'ok': True,\n",
        "            'optimized': optimized,\n",
        "            'missing_vars': missing_vars if missing_vars else None\n",
        "        })\n",
        "\n",
        "    except Exception as e:\n",
        "        return jsonify({'ok': False, 'error': str(e)}), 500\n",
        "\n",
    ]
    
    lines[start:end] = new_func_lines
    
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
    for j in range(max(0, e.lineno-5), min(e.lineno+6, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
