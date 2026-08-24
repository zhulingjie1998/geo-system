"""Show exact bytes of lines 1018-1050"""
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
with open(fp, 'rb') as f:
    lines = f.readlines()

for i in range(1017, min(1060, len(lines))):
    line = lines[i]
    print(f'L{i+1}: {line}')
