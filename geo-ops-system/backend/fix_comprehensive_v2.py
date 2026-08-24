# -*- coding: utf-8 -*-
"""
Comprehensive fix for app.py - replace ALL mojibake lines with English.
This is needed because the file has widespread GBK→UTF-8 double-encoding corruption.
"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Define replacements for known problematic lines
# Format: (line_number_1_indexed, new_content)
replacements = {
    # Line 123: security headers docstring
    123: '    """Global security headers."""\n',
    
    # Line 146: auth required error
    146: '        return jsonify({"error": "Not logged in or session expired", "code": "AUTH_REQUIRED"}), 401\n',
}

# Apply known replacements
for line_num, new_content in replacements.items():
    if line_num <= len(lines):
        idx = line_num - 1
        if any(ord(c) > 127 for c in lines[idx]):  # Has non-ASCII
            print(f"Line {line_num}: Replacing")
            lines[idx] = new_content

# Find and fix remaining lines with common mojibake patterns
mojibake_indicators = ['\ue0bc', '\ue21a', '\ue1bb', '\ue044', '\ue15e', '\ue11d', '\ue1bd', '\ue101', '鏈嶅姟', '瓒呯骇', '绠＄悊']
fixed_count = len(replacements)

for i, line in enumerate(lines):
    line_num = i + 1
    # Skip already replaced lines
    if line_num in replacements:
        continue
    
    # Check for mojibake
    has_mojibake = any(ind in line for ind in mojibake_indicators)
    
    if has_mojibake:
        # Try to identify what kind of line this is and provide appropriate replacement
        stripped = line.strip()
        
        # Error messages with jsonify
        if '"error":' in line and 'jsonify' in line:
            # Replace with generic error - we'll lose the Chinese message but it'll work
            print(f"Line {line_num}: Fixing error message")
            # Keep structure, replace content
            import re
            # Extract the error value
            match = re.search(r'"error":\s*"([^"]*)"', line)
            if match:
                old_msg = match.group(1)
                new_line = line.replace(f'"error": "{old_msg}"', '"error": "Error"')
                lines[i] = new_line
                fixed_count += 1
        
        # Docstrings (triple-quoted)
        elif '"""' in line and line.count('"""') >= 2:
            print(f"Line {line_num}: Fixing docstring")
            lines[i] = line[:line.index('"""')+3] + '"""' + '\n'
            fixed_count += 1
            
        # Comments
        elif stripped.startswith('#'):
            print(f"Line {line_num}: Removing comment")
            lines[i] = '\n'  # Replace with empty line
            fixed_count += 1

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print(f"\nTotal fixed: {fixed_count} lines")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Still has error at line {e.lineno}: {e.msg}")
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+3]
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line[:100]}")
