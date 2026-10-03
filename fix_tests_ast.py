import ast
import os

directories = ['alumnos', 'tests', 'user_profesor']
bad_kwargs = {'nombre', 'rut', 'direccion', 'fecha_nacimiento', 'correo_electronico', 'telefono', 'genero'}

class FixTests(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'create':
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'objects':
                if isinstance(node.func.value.value, ast.Name):
                    model_name = node.func.value.value.id
                    if model_name in ('Alumno', 'Profesor', 'Tutor'):
                        new_keywords = []
                        for kw in node.keywords:
                            if kw.arg not in bad_kwargs:
                                if model_name == 'Profesor' and kw.arg == 'especialidad' and isinstance(kw.value, ast.Constant):
                                    # Change especialidad='Matematicas' to Especialidad.objects.get_or_create(nombre='Matematicas')[0]
                                    new_value = ast.Subscript(
                                        value=ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Attribute(value=ast.Name(id='Especialidad', ctx=ast.Load()), attr='objects', ctx=ast.Load()),
                                                attr='get_or_create', ctx=ast.Load()
                                            ),
                                            args=[],
                                            keywords=[ast.keyword(arg='nombre', value=kw.value)]
                                        ),
                                        slice=ast.Constant(value=0),
                                        ctx=ast.Load()
                                    )
                                    new_keywords.append(ast.keyword(arg='especialidad', value=new_value))
                                else:
                                    new_keywords.append(kw)
                        node.keywords = new_keywords
        return node

for root, dirs, files in os.walk('.'):
    if 'migrations' in root or '.venv' in root or 'Lib' in root: continue
    for file in files:
        if (file.startswith('test') and file.endswith('.py')) or file == 'tests.py':
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
                tree = FixTests().visit(tree)
                new_content = ast.unparse(tree)
                
                if 'Especialidad' not in new_content:
                    new_content = 'from alumnos.models import Especialidad\n' + new_content
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated AST for {path}")
            except Exception as e:
                print(f"Error parsing {path}: {e}")
