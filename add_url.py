import os

filepath = 'alumnos/urls.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'sala_virtual' not in content:
    # Add import
    content = content.replace('from .views import (', 'from .views import (\n    sala_virtual,')
    # Add path
    content = content.replace('urlpatterns = [', "urlpatterns = [\n    path('sala-virtual/<int:clase_id>/', sala_virtual, name='sala_virtual'),")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
