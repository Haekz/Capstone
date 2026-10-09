import os

filepath = 'alumnos/templates/alumnos/Alumno_pag1.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_btn = '''<button class="btn-join-class ap-flex-1" onclick="joinVideoCall('{{ insc.clase.profesor.user.first_name }}', 'https://meet.google.com/lbwus-class-{{ insc.clase.id_clase }}')">
                                            <i class="bi bi-camera-video-fill"></i> Unirse a la Clase
                                        </button>'''

new_btn = '''<a class="btn-join-class ap-flex-1" href="{% url 'sala_virtual' insc.clase.id_clase %}" style="display:flex; justify-content:center; align-items:center; text-decoration:none;">
                                            <i class="bi bi-camera-video-fill"></i> Unirse a la Clase
                                        </a>'''

content = content.replace(old_btn, new_btn)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
