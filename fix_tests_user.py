import os
import re

directories = ['alumnos', 'tests', 'user_profesor', 'admin_portal']

for d in directories:
    for root, dirs, files in os.walk(d):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'from django.contrib.auth.models import User' in content:
                    content = content.replace('from django.contrib.auth.models import User', 'from django.contrib.auth import get_user_model\nUser = get_user_model()')
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Updated {filepath}")
