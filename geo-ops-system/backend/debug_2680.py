# -*- coding: utf-8 -*-
"""查看第2680-2710行找到问题根源"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")
print("\n=== 第2680-2720行 ===")
for i in range(2679, 2720):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
