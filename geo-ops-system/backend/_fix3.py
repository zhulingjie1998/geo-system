import re, subprocess, sys, os
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
px = sys.executable
out = r'C:\Users\Administrator\Desktop\fix_log.txt'

def bad(s):
    for c in s:
        o=ord(c)
        if o>127 and((0x2E80<=o<=0x2FDF)or(0xF900<=o<=0xFAFF)or(0x3200<=o<=0x32FF)or(0xFF00<=o<=0xFFEF)or(0xE000<=o<=0xF8FF)):
            return 1
    return 0

with open(out,'w',encoding='utf-8') as log:
    for i in range(200):
        r=subprocess.run([px,'-m','py_compile',fp],capture_output=True,text=True)
        if r.returncode==0:
            log.write(f'SUCCESS after {i} fixes\n')
            break
        m=re.search(r'line (\d+)',r.stderr)
        if not m:
            log.write('ERR:'+r.stderr[:150]+'\n')
            break
        ln=int(m.group(1))
        with open(fp,'r',encoding='utf-8') as f: lines=f.readlines()
        if ln>len(lines): log.write('OOR\n');break
        L=lines[ln-1].rstrip()
        log.write(f'{i} L{ln}: {L[:70]}\n')
        fixed=False
        if '"""' in L and bad(L):
            lines[ln-1]=re.sub(r'""".*?"""','""""""',L)+'\n'
            fixed=True
        elif not fixed and bad(L):
            def replacer(m):
                s=m.group(0)
                if bad(s): return '""'
                return s
            newL=re.sub(r'"[^"]*"',replacer,L)
            if newL!=L:
                lines[ln-1]=newL+'\n'
                fixed=True
        if fixed:
            with open(fp,'w',encoding='utf-8') as f: f.writelines(lines)
        else:
            log.write(f'CANNOT FIX: {L}\n')
            break
    log.flush()
print('Done. See fix_log.txt')
