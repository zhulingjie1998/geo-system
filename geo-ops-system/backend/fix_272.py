# -*- coding: utf-8 -*-
"""修复第272行 - })和注释混在一起"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("第272行原始:")
print(repr(lines[271]))

# 修复第272行 - 分离代码和注释
lines[271] = '        "permissions":   pages,  # alias for frontend\n'

# 添加独立的闭合行
lines.insert(272, '    })\n')

print("\n修复后:")
print("272:", repr(lines[271]))
print("273:", repr(lines[272]))

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
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
