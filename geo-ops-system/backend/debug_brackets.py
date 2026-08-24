# -*- coding: utf-8 -*-
"""Debug: find unclosed brackets/parens before line 121"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check for unclosed structures in first 120 lines
code = ''.join(lines[:120])

# Count brackets
open_parens = code.count('(') - code.count(')')
open_brackets = code.count('[') - code.count(']')
open_braces = code.count('{') - code.count('}')

print(f"Before line 121:")
print(f"  Parentheses balance: {open_parens}")
print(f"  Brackets balance: {open_brackets}")
print(f"  Braces balance: {open_braces}")

# Check for unclosed strings
in_string = False
string_char = None
for i, ch in enumerate(code):
    if in_string:
        if ch == string_char and (i == 0 or code[i-1] != '\\'):
            in_string = False
    elif ch in ('"', "'"):
        in_string = True
        string_char = ch

if in_string:
    print("  WARNING: Unclosed string detected!")
else:
    print("  Strings: OK")

# Show lines 115-122
print("\nLines 115-122:")
for i in range(114, min(122, len(lines))):
    print(f"{i+1}: {lines[i][:100].rstrip()}")
