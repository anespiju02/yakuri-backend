import json
import sys
from pathlib import Path

# Asegura que Python reconozca la carpeta raíz del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app

output_path = ROOT_DIR / "openapi.json"
output_path.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Contrato OpenAPI exportado exitosamente en: {output_path}")
