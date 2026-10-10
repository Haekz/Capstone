import os

filepath = 'alumnos/templates/alumnos/sala_virtual.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("https://meet.ffmuc.net/external_api.js", "https://meet.jit.si/external_api.js")
content = content.replace("const domain = 'meet.ffmuc.net';", "const domain = 'meet.jit.si';")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
