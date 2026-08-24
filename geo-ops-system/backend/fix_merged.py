# -*- coding: utf-8 -*-
"""
Fix remaining issues: lines where comments are merged with code
"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find lines that have both # comment and actual code (merged due to corruption)
fixed = 0
for i, line in enumerate(lines):
    # Pattern: starts with spaces, then #, then Chinese mojibake, then actual Python code
    # Example: "    # 浠呭湪 HTTPS 鎵嶇敓鏁堬紙HSTS锛?    resp.headers..."
    stripped = line.lstrip()
    
    if stripped.startswith('#') and any(ord(c) > 127 for c in line):
        # Check if there's code after the corrupted comment
        # Look for patterns like:    resp.headers,    return,    db., etc.
        import re
        
        # Find where the actual code might start (after multiple spaces following the comment)
        match = re.search(r'[^\x20-\x7e]\s{4,}(resp|return|db\.|logger|if |for |with )', line)
        if match:
            # Extract just the code part
            code_start = match.start() + len(match.group()[:match.group().index(resp|return|db\.|logger|if |for |with )])
            # Actually let's just find the code part more reliably
            
            print(f"Line {i+1}: Merged comment+code detected")
            print(f"  Original: {line[:120].rstrip()}...")
            
            # Try to extract code part - look for known Python patterns
            code_match = re.search(r'\s{4,}(resp|return|db\.|logger|if |def |class |with |for |import )', line)
            if code_match:
                # Get everything from the code start
                code_part = line[code_match.start():]
                # Make sure it's properly indented
                if not code_part.startswith('    '):
                    code_part = '    ' + code_part.lstrip()
                
                lines[i] = code_part
                print(f"  -> Code extracted: {code_part.rstrip()[:80]}")
                fixed += 1

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print(f"\nFixed {fix} merged lines")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Error at line {e.lineno}: {e.msg}")
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+3]
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line[:100]}")
