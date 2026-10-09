import os

filepath = 'alumnos/templates/alumnos/sala_virtual.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix JS syntax error caused by PowerShell string expansion
bad_fetch = "fetch(/alumnos/sala-virtual//iniciar/, {"
good_fetch = "fetch('/alumnos/sala-virtual/' + claseId + '/iniciar/', {"

content = content.replace(bad_fetch, good_fetch)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
