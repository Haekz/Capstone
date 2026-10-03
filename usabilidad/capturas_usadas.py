"""Lista las capturas que usa REGISTRO_USABILIDAD.html (para commitear solo esas)."""
import re
from pathlib import Path

AQUI = Path(__file__).parent
html = (AQUI / 'REGISTRO_USABILIDAD.html').read_text(encoding='utf-8')
usadas = sorted(set(re.findall(r'src="(capturas/[^"]+)"', html)))
peso = sum((AQUI / u).stat().st_size for u in usadas) / 1e6
print(f'{len(usadas)} capturas, {peso:.1f} MB')
for u in usadas:
    print(f'usabilidad/{u}')
