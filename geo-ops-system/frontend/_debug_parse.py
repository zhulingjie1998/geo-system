import re

with open(r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\frontend\src\views\PublishAiWritePage.vue', 'r', encoding='utf-8') as f:
    c = f.read()

t_start = c.index('<template>')
script_start = c.index('<script setup>')
template = c[t_start:script_start]

# Write template to temp file
with open(r'C:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\frontend\_template_only.html', 'w', encoding='utf-8') as f:
    f.write(template)

print(f'Template extracted ({len(template)} chars) to _template_only.html')

# Now check for any unclosed tags using a simple stack approach
void_tags = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
stack = []

# Find all tags
for m in re.finditer(r'<(/?)(\w+)[^>]*?(/?)>', template):
    slash1 = m.group(1)  # opening /
    tag = m.group(2).lower()
    slash2 = m.group(3)  # closing / (self-close)
    
    if tag in void_tags or slash2 == '/':
        continue
    
    if slash1 == '/':
        # Find matching open tag
        found = False
        for i in range(len(stack)-1, -1, -1):
            if stack[i] == tag:
                stack.pop(i)
                found = True
                break
        if not found:
            print(f'WARNING: Closing </{tag}> at pos {m.start()} has no matching open!')
    else:
        stack.append(tag)

if stack:
    print(f'\nUNCLOSED TAGS ({len(stack)}):')
    for t in stack[-20:]:
        print(f'  <{t}>')
else:
    print('\nAll tags properly closed!')
