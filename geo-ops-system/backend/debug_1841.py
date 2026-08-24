# -*- coding: utf-8 -*-
"""查看第1830-1860行的代码结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")
print("\n=== 第1830-1870行 ===")
for i in range(1829, 1870):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
