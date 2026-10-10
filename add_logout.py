import os

# user_profesor/views.py
filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'def logout_prof' not in content:
    logout_code = '''
from django.contrib.auth import logout as auth_logout

def logout_prof(request):
    auth_logout(request)
    return redirect('home')
'''
    content += logout_code
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# user_profesor/urls.py
filepath = 'user_profesor/urls.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'logout_prof' not in content:
    content = content.replace("from .views import ", "from .views import logout_prof, ")
    content = content.replace("]", "    path('logout', logout_prof, name='logout_prof'),\n]")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Added logout_prof")
