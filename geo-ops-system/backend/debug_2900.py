# -*- coding: utf-8 -*-
"""修复第2905行的未闭合三引号"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 查看第2900-2925行
print("\n=== 第2900-2930行 ===")
for i in range(2899, 2930):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()[:120]}")
