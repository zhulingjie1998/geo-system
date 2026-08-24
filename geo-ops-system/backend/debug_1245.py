# -*- coding: utf-8 -*-
"""修复第1245行括号不匹配问题"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 第284行附近 ===")
for i in range(280, 290):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

print("\n=== 第1240-1250行 ===")
for i in range(1239, 1252):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
