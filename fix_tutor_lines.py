import sys

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'tutor = Tutor.objects.create(' in line:
        new_lines.append(line)
        new_lines.append('                user=user\n')
        new_lines.append('            )\n')
        skip = True
        continue
    
    if skip:
        if ')' in line and 'genero=genero_obj' not in line:
            # wait, how to safely stop skipping?
            pass
        if line.strip() == ')':
            skip = False
        continue
        
    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Line replacement done.")
