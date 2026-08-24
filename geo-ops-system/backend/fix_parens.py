# -*- coding: utf-8 -*-
"""修复第281、284行缺失的括号"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复第281行 - 缺少 ), 400
if 'return jsonify({"error": "Error"}' in lines[280] and lines[280].rstrip().endswith('"Error"}'):
    lines[280] = '        return jsonify({"error": "Error"}), 400\n'
    print("✓ 第281行已修复")

# 修复第284行 - 缺少 ), 401  
if 'return jsonify({"error": "Error"}' in lines[283] and lines[283].rstrip().endswith('"Error"}'):
    lines[283] = '        return jsonify({"error": "Error"}), 401\n'
    print("✓ 第284行已修复")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓✓✓ 语法正确! ✓✓✓")
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-2), min(e.lineno+3, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
