import re, subprocess, sys
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
px = sys.executable

def bad(s):
    for c in s:
        o=ord(c)
        if o>127 and((0x2E80<=o<=0x2FDF)or(0xF900<=o<=0xFAFF)or(0x3200<=o<=0x32FF)or(0xFF00<=o<=0xFFEF)or(0xE000<=o<=0xF8FF)):
            return 1
    return 0

for i in range(200):
    r=subprocess.run([px,'-m','py_compile',fp],capture_output=True,text=True)
    if r.returncode==0:
        print(f'SUCCESS after {i} fixes')
        break
    m=re.search(r'line (\d+)',r.stderr)
    if not m:
        print('ERR:'+r.stderr[:150])
        break
    ln=int(m.group(1))
    with open(fp,'r',encoding='utf-8') as f: lines=f.readlines()
    if ln>len(lines): print('OOR');break
    L=lines[ln-1].rstrip()
    print(f'{i} L{ln}: {L[:70]}')
    
    fixed=False
    
    # Fix docstrings
    if '"""' in L and bad(L):
        lines[ln-1]=re.sub(r'""".*?"""','""""""',L)+'\n'
        fixed=True
    
    # Fix garbled Chinese in regular strings like "瀹㈡埛"
    elif not fixed and bad(L):
        # Replace each garbled string with empty string or placeholder
        def replacer(m):
            s=m.group(0)
            if bad(s):
                return '""'
            return s
        newL=re.sub(r'"[^"]*"',replacer,L)
        if newL!=L:
            lines[ln-1]=newL+'\n'
            fixed=True
    
    if fixed:
        with open(fp,'w',encoding='utf-8') as f: f.writelines(lines)
    else:
        print('CANNOT FIX')
        # Show more context
        print(f'Full line: {L}')
        break
