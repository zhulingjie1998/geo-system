# -*- coding: utf-8 -*-
"""Comprehensive fix for ALL encoding issues in app.py"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find and list all lines with common mojibake patterns
mojibake_patterns = [
    '\ue0bc', '\ue21a', '\ue1bb', '\ue044', '\ue15e', '\ue11d', '\ue1bd', '\ue101',
    '鏈嶅姟', '瓒呯骇', '绠＄悊', '绯荤粺', '鍐呯疆', '鎻愮ず', '璇风珛', '淇敼',
]

fixed_count = 0
problem_lines = []

for i, line in enumerate(lines):
    has_mojibake = any(p in line for p in mojibake_patterns)
    if has_mojibake:
        problem_lines.append(i+1)
        print(f"Line {i+1}: {line[:100].rstrip()}...")

print(f"\nFound {len(problem_lines)} lines with potential issues")
