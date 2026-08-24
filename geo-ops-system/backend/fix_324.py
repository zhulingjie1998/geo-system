# -*- coding: utf-8 -*-
"""强制修复第324行的非法字符"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

# 用字节模式读取，找到并删除非法字符
with open(filepath, 'rb') as f:
    data = f.read()

# 找到第324行（大约位置）
lines = data.split(b'\n')
print(f"总行数: {len(lines)}")
print(f"第324行 (index 323):")
line_324 = lines[323]
print(f"原始字节: {line_324[:120]}")

# 查找U+E06C字符的字节序列
bad_char = b'\xec\x81\xac'  # U+E06C in UTF-8
if bad_char in line_324:
    print(f"找到非法字符!")
    # 删除这个字符
    new_line = line_324.replace(bad_char, b'')
    lines[323] = new_line
    print(f"已移除非法字符")
else:
    print(f"未找到预期字节，尝试其他方法...")
    # 直接替换整行为英文docstring
    lines[323] = b'    """Frontend menu + backend optional sub-menu shared. Super_admin expands all."""\n'
    print(f"替换为英文")

# 写回
data_out = b'\n'.join(lines)
with open(filepath, 'wb') as f:
    f.write(data_out)

print("\n验证语法...")
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓✓✓ 语法正确! ✓✓✓")
except SyntaxError as e:
    print(f"✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-2), min(e.lineno+2, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:90]}")
