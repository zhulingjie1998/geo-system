# -*- coding: utf-8 -*-
"""修复中文标点问题"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到并替换第2919行的文档字符串
for i in range(len(lines)):
    if 'themed HTML' in lines[i] and 'chromium' in lines[i]:
        indent = len(lines[i]) - len(lines[i].lstrip())
        lines[i] = ' ' * indent + '"""themed HTML -> chromium renders PDF (subprocess isolation) -> attachment download."""\n'
        print(f"修复第{i+1}行")
        break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证
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
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
