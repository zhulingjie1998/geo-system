# -*- coding: utf-8 -*-
"""查看第1230-1260行的代码"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 第1225-1260行 ===")
for i in range(1224, 1260):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
