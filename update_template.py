import os
import re

filepath = 'user_profesor/templates/user_profesor/panel_profesor.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Make form multipart
content = content.replace('method="POST" class="prof-form">', 'method="POST" class="prof-form" enctype="multipart/form-data">')

# Add Profile Picture field
foto_html = '''
                    <div class="prof-form-group" style="text-align: center; margin-bottom: 25px;">
                        {% if profesor.user.foto_perfil %}
                            <img src="{{ profesor.user.foto_perfil.url }}" alt="Foto de Perfil" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; margin-bottom: 15px; border: 3px solid var(--primary);">
                        {% else %}
                            <div style="width: 120px; height: 120px; border-radius: 50%; background: var(--bg-card); display: flex; align-items: center; justify-content: center; margin: 0 auto 15px auto; border: 3px dashed var(--border);">
                                <i class="bi bi-person" style="font-size: 3rem; color: var(--text-muted);"></i>
                            </div>
                        {% endif %}
                        <label for="prof-foto" class="prof-form-label" style="display: block;">Subir Foto de Perfil (Pública)</label>
                        <input type="file" id="prof-foto" name="foto_perfil" class="prof-form-input" accept="image/*" style="border: none; padding: 0;">
                    </div>
'''
content = content.replace('{% csrf_token %}', '{% csrf_token %}' + foto_html)

# Add (Privado) labels
content = content.replace('<label for="prof-rut" class="prof-form-label">RUT</label>', '<label for="prof-rut" class="prof-form-label">RUT <span style="color:var(--text-muted); font-size:0.8rem;">(Solo visible para ti)</span></label>')
content = re.sub(r'<label for="prof-direccion" class="prof-form-label">Direcci.n</label>', '<label for="prof-direccion" class="prof-form-label">Dirección <span style="color:var(--text-muted); font-size:0.8rem;">(Solo visible para ti)</span></label>', content)

# Fix Name field to send combined name since view splits it
content = content.replace('value="{{ profesor.user.first_name }}"', 'value="{{ profesor.user.first_name }} {{ profesor.user.last_name }}"')

# Add switch for Telefono
tel_switch = '''
                        <div style="margin-top: 8px; display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="prof-tel-publico" name="telefono_publico" {% if profesor.telefono_publico %}checked{% endif %}>
                            <label for="prof-tel-publico" style="font-size: 0.85rem; color: var(--text-muted); cursor: pointer;">Hacer público para los alumnos</label>
                        </div>
'''
content = re.sub(r'(<input type="tel" id="prof-telefono" name="telefono"[^>]+>)', r'\1' + tel_switch, content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated template")
