# Pruebas

La suite corre con `python manage.py test` (runner de Django) o con `pytest`: las dos encuentran las mismas pruebas y aplican los mismos ajustes (`lbwus/test_runner.py` y `conftest.py`).

## Requisitos

- **PostgreSQL** en `DATABASE_URL`. Django crea y borra una base `test_<nombre>` en ese servidor: nunca apuntarlo a la base de produccion.
- **Sin `MONGODB_URI` real.** Las pruebas normales usan mongomock. El `activate` del entorno puede exportar la URI de Atlas: quitala antes (`unset MONGODB_URI`).
- **Sin `SITIO_CLAVE`.** Con la puerta activa, las demas pruebas no la pasan y fallan.
- Herramientas de QA: `pip install -r requirements-dev.txt` (incluye `requirements.txt`). Produccion no instala este archivo.

```bash
source .venv/bin/activate
unset MONGODB_URI SITIO_CLAVE
export DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus
```

## Comandos

```bash
python manage.py test                       # runner de Django
pytest                                      # misma suite, orden fijo
pytest tests/test_paquetes.py               # un archivo
pytest tests/test_paquetes.py::CompraTests  # una clase
pytest -k webpay                            # por nombre
pytest -n auto                              # en paralelo (pytest-xdist)
pytest -p randomly                          # orden aleatorio (pytest-randomly)
pytest -p randomly --randomly-seed=1234     # repetir un orden aleatorio que fallo
pytest --lf                                 # solo las que fallaron la ultima vez
```

Reporte HTML de una corrida (pytest-html): `pytest --html=reporte.html --self-contained-html`.

Referencia (07-11-2026, `main` en 4aa8239, `manage.py test`): 1.548 pruebas, 1.542 pasan y 6 omitidas (Atlas), sin fallos esperados. Los tiempos que siguen son de la medición del 05-11 (`main` en 74e8480, 1.355 pruebas, PostgreSQL 16 local). `manage.py test` tarda unos 12 min, `pytest` unos 10 y `pytest -n auto` unos 2.

`pytest.ini` desactiva `pytest-randomly` por omision (`-p no:randomly`) para que el orden sea el mismo de `manage.py test`. Una prueba que solo falla con `-p randomly` o con `-n auto` depende del orden o comparte estado con otra: se reporta, no se esconde.

## Marcadores

| Marcador | Que marca | Como se usa |
|---|---|---|
| `integracion_atlas` | `comunidad/tests/test_atlas.py`, contra Atlas real | Se omiten sin `MONGODB_URI` y `MONGODB_INTEGRACION=1`. `pytest -m "not integracion_atlas"` |
| `postgres` | `tests/test_concurrencia_inscripcion.py` (bloqueos y concurrencia reales) | `pytest -m postgres` |
| `lento` | Pruebas de mas de un segundo | `pytest -m "not lento"` |

Los dos primeros se asignan por archivo en `conftest.py` (`MARCADORES_POR_MODULO`). `--strict-markers` rechaza un marcador que no este declarado en `pytest.ini`.

## Cobertura

```bash
pytest --cov=. --cov-branch --cov-report=term-missing --cov-report=html:cobertura_html
```

`.coveragerc` deja fuera `.venv`, migraciones, pruebas, `usabilidad/` y `manage.py`. El reporte HTML queda en `cobertura_html/index.html` (no se versiona).

## Analisis estatico

```bash
bandit -r . -x ./.venv,./tests,*/migrations       # seguridad del codigo
pip-audit -r requirements.txt                     # vulnerabilidades conocidas en dependencias
ruff check . --extend-select B,S,DJ               # errores, bugs probables, seguridad y Django
python manage.py makemigrations --check --dry-run # modelos sin migracion
```

## Pruebas que documentan un bug

Una prueba que descubre un bug sin corregir se marca con `@bug_qa('BUG-QA-NN', 'motivo')` (`tests/bugs_qa.py`). Con pytest es `pytest.mark.xfail(strict=True)`; con `manage.py test`, `unittest.expectedFailure` (`conftest.py` elige cual). Se usa una sola de las dos a la vez: juntas, pytest toma el "exito inesperado" de unittest como el fallo esperado y no avisa.

En los dos runners la suite falla cuando el bug se corrige y la prueba empieza a pasar (XPASS estricto / *unexpected success*): en ese momento se quita la marca. Para ver el fallo real de una prueba marcada: `pytest --runxfail tests/test_qa_pagos.py`.

## Matriz de acceso por rol

`tests/test_qa_acceso.py` recorre todas las rutas del proyecto (`tests/rutas_qa.py`) como anonimo y como cada rol, y falla si alguien recibe 200 fuera de lo publico, lo comun o lo propio de su rol, o si alguna ruta da 500. **Si agregas una ruta, agregala a `PUBLICAS`, `COMUNES` o `PROPIAS`**: la prueba falla hasta entonces a proposito (regla 1).
