# -*- coding: utf-8 -*-
"""查看第264行附近的代码"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 第260-280行 ===")
for i in range(259, 285):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
