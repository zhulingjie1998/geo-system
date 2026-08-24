# -*- coding: utf-8 -*-
"""查看第3125-3150行"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")
print("\n=== 第3120-3161行 ===")
for i in range(3119, 3161):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()[:120]}")
