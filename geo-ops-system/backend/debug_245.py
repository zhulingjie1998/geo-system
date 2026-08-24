# -*- coding: utf-8 -*-
"""查看第240-280行的代码结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")
print("\n=== 第235-285行 ===")
for i in range(234, 285):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
