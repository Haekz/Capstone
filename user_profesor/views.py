from django.shortcuts import render

# --- Vistas movidas desde alumnos ---
def regis_prof(request):
    context = {}
    return render(request, 'user_profesor/regis_prof.html', context)

def regis_tutor(request):
    context = {}
    return render(request, 'user_profesor/regis_tutor.html', context)
