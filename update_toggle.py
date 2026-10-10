import os
import re

filepath = 'user_profesor/templates/user_profesor/panel_profesor.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the simple checkbox with a CSS toggle switch
old_switch = '''
                        <div style="margin-top: 8px; display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="prof-tel-publico" name="telefono_publico" {% if profesor.telefono_publico %}checked{% endif %}>
                            <label for="prof-tel-publico" style="font-size: 0.85rem; color: var(--text-muted); cursor: pointer;">Hacer público para los alumnos</label>
                        </div>
'''

new_switch = '''
                        <div style="margin-top: 10px; display: flex; align-items: center; gap: 12px;">
                            <label class="toggle-switch">
                                <input type="checkbox" id="prof-tel-publico" name="telefono_publico" {% if profesor.telefono_publico %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                            <label for="prof-tel-publico" style="font-size: 0.85rem; color: var(--text-muted); cursor: pointer;">Hacer público para los alumnos</label>
                        </div>
'''

content = content.replace(old_switch, new_switch)

# Add CSS for the toggle switch if not already present
css = '''
<style>
/* CSS Toggle Switch */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .4s;
  border-radius: 24px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}
input:checked + .slider {
  background-color: var(--primary); /* usa el morado de tu paleta */
}
input:checked + .slider:before {
  transform: translateX(20px);
}
</style>
'''

if '/* CSS Toggle Switch */' not in content:
    content = content.replace('{% block content %}', '{% block content %}\n' + css)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Added toggle switch")
