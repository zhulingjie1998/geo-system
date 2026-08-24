# -*- coding: utf-8 -*-
"""查看第253-280行的代码结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 第253-285行 ===")
for i in range(252, 285):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
