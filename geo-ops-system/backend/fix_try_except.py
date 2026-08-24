# -*- coding: utf-8 -*-
"""修复api_auth_me函数的try/except结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 修复前 ===")
for i in range(254, 276):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 问题：
# 第256行 return 后面应该结束if块
# 第258-261行应该是try块的内容，但缺少try:
# 第262行是孤立的except

# 修复方案：在258行前插入try:，并确保缩进正确
# 当前第258行（index 257）是 "        uid = session.get..."

# 在第257行前插入 try:
lines.insert(257, '    try:\n')

# 确保第259-262行（原258-261）有正确的缩进（12空格）
for i in range(258, 262):
    if i < len(lines):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith('#'):
            # 保持至少12空格缩进
            if len(lines[i]) - len(stripped) < 8:
                lines[i] = '            ' + stripped + '\n'

print("\n=== 修复后 ===")
for i in range(254, 280):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

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
