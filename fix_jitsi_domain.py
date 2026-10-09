import os

filepath = 'alumnos/templates/alumnos/sala_virtual.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Jitsi domain
content = content.replace("https://meet.jit.si/external_api.js", "https://meet.ffmuc.net/external_api.js")
content = content.replace("const domain = 'meet.jit.si';", "const domain = 'meet.ffmuc.net';")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
