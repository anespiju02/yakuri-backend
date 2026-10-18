# Yakuri — Backend

API en FastAPI que estima el **impacto hídrico** de productos de limpieza y cuidado
personal a partir del texto de su etiqueta, con un motor de puntaje ético y auditable.
Es el backend del proyecto académico *Yakuri* (Maestría en Inteligencia Artificial,
Universidad Continental, Perú).

**API en producción:** https://yakuri-backend.onrender.com
**Documentación interactiva (Swagger):** https://yakuri-backend.onrender.com/docs
**Frontend asociado:** https://github.com/anespiju02/yakuri-frontend

## Qué resuelve

Las listas de ingredientes de los productos de limpieza y cuidado personal usan
nomenclatura técnica (INCI) que no le dice a un consumidor promedio qué tan dañino es
un producto para el agua tras su uso y descarte. Yakuri recibe ese texto, identifica
los ingredientes, calcula un índice de impacto hídrico de **A** (bajo impacto) a **E**
(alto impacto) y genera una explicación en español claro, basada únicamente en
evidencia científica documentada — nunca en afirmaciones inventadas.

## Principios de diseño (y cómo se verifican)

El proyecto nace de un curso de ética en IA, así que estas reglas son requisitos
funcionales, no buenas intenciones:

| Regla | Qué garantiza | Dónde se verifica |
|---|---|---|
| **6.1 — Independencia comercial** | La marca y el precio nunca influyen en el puntaje | `tests/test_ethics.py::test_rule_6_1_commercial_independence` |
| **6.2 — Manejo de datos insuficientes** | Un ingrediente sin evidencia científica suficiente se excluye del cálculo, nunca se penaliza por defecto | `tests/test_ethics.py::test_rule_6_2_insufficient_data_handling` |
| **6.3 — Prueba de sustitución de marca** | El mismo listado de ingredientes, con distinta marca/precio inyectados, siempre produce el mismo resultado | `POST /api/v1/auditorias-eticas/sustitucion-marca` y `test_rule_6_3_brand_substitution_suite` |
| **Trazabilidad** | Todo ingrediente usado en el cálculo expone su fuente y fecha de revisión | Campo `source` / `last_reviewed` en cada `IngredienteDto` |

## Arquitectura

```
app/
├── main.py                 # Punto de entrada FastAPI, registro de routers, CORS
├── models.py                # Esquemas Pydantic (contrato de la API)
├── database.py               # Base de ingredientes semilla (ver "Estado actual")
├── sqlite_repo.py            # Persistencia en SQLite (ingredientes + historial de escaneos)
├── services/
│   ├── nlp_matcher.py         # Identifica ingredientes en el texto de la etiqueta
│   ├── scoring.py             # Calcula el índice de impacto hídrico (A–E)
│   ├── rag_explainer.py       # Genera la explicación en lenguaje natural
│   └── ocr_service.py         # Extrae texto desde una foto de etiqueta
└── routers/
    ├── ingredientes.py        # CRUD y búsqueda sobre la base científica
    ├── escaneos.py            # Analiza una etiqueta (texto o imagen)
    ├── auditorias_eticas.py   # Ejecuta la prueba de sustitución de marca
    └── metricas.py            # Indicadores de éxito del prototipo
```

## Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/v1/escaneos/texto` | Analiza el texto de una etiqueta y devuelve índice A-E + explicación |
| `POST` | `/api/v1/escaneos/imagen` | Igual, pero a partir de una foto (OCR) |
| `GET` | `/api/v1/escaneos` | Lista el historial de escaneos guardados |
| `GET` | `/api/v1/ingredientes` | Lista/filtra/busca en la base científica de ingredientes |
| `POST` | `/api/v1/ingredientes` | Registra un nuevo ingrediente |
| `POST` | `/api/v1/auditorias-eticas/sustitucion-marca` | Corre la prueba de invarianza de marca (regla 6.3) |
| `GET` | `/api/v1/metricas/criterios-exito` | Indicadores de éxito del prototipo (% explicado, % consistencia) |
| `GET` | `/api/v1/salud` | Health check |

La especificación OpenAPI 3.1 completa está disponible en `/docs` y se usa para
generar automáticamente el cliente TypeScript del frontend.

## Estado actual del prototipo (honesto, no aspiracional)

Este backend es un **prototipo funcional de maestría**, no un producto terminado. El
informe académico describe una arquitectura de PLN más avanzada (embeddings profundos fine-tuned,
modelos de secuencia, NER de claims, explicabilidad con LIME/SHAP); lo que hoy está efectivamente
implementado y probado es:

- **Identificación de ingredientes (PLN en dos fases):**
  - **Fase 1 (Difusa):** Coincidencia exacta y difusa de caracteres mediante `rapidfuzz` (umbral >= 82.0).
  - **Fase 2 (Semántica ligera):** Si `rapidfuzz` no alcanza el umbral, se activa una segunda pasada
    usando similitud cosenoidal de embeddings multilingües (`sentence-transformers` con el modelo
    `paraphrase-multilingual-MiniLM-L12-v2`, ~120MB, umbral coseno >= 0.72). Los embeddings del catálogo
    se precalculan en memoria durante el ciclo de vida de la aplicación (`lifespan`).
  - **Manejo de fallos (Fallback resiliente):** Si el modelo no puede cargarse por límites de memoria
    (p.ej. plan gratuito de Render), el sistema degrada automáticamente a solo-fuzzy sin interrumpir el servicio.
- **Transparencia y Explicabilidad (XAI en la API):**
  - Cada respuesta de la API (`ResultadoEscaneoDto`) expone con total transparencia cómo se obtuvo cada resultado:
    - `generation_method`: Método de redacción de la explicación (`"plantilla_grounded"`).
    - `ocr_method`: Origen del texto analizado (`"modelo_ocr_real"`, `"modelo_ocr_fallback"` o `"texto_directo"`).
    - `matching_method`: Método de extracción PLN predominante (`"matching_fuzzy"`, `"matching_semantico"` o `"hibrido_fuzzy_semantico"`).
    - `traceability_details`: Cada ingrediente individual reporta su `match_method` (`"fuzzy"` o `"semantico"`).
- **Motor de puntaje:** Promedio ponderado (0 a 1) por ingrediente verificado, mapeado a un grado A-E
  por umbrales fijos.
- **Generación de explicación (LLM Grounded con Red de Seguridad):**
  - **Motor Principal:** Integración con **Gemini API** (`google-genai` con modelo `gemini-2.5-flash`), utilizando un prompt restringido que recibe exclusivamente los ingredientes verificados, el grado A-E y las justificaciones científicas (sin marca ni precio, cumpliendo la Regla 6.1).
  - **Salvaguarda contra Alucinaciones (Validación Posterior):** Antes de retornar la respuesta generada por el LLM, el sistema audita que el texto no mencione ningún ingrediente químico (`inci_name`) que no pertenezca a la fórmula analizada.
  - **Respaldo Determinista Automático:** Si no hay API key configurada, hay fallos de red o la validación detecta una alucinación, el sistema conmuta automáticamente al generador basado en plantillas, asegurando cero alucinaciones y alta disponibilidad.
  - **Transparencia en Respuesta:** `generation_method` indica explícitamente si la explicación fue `"llm_grounded"` o `"plantilla_grounded"`.
- **OCR:** Tesseract OCR (con paquete español e inglés instalado en Docker), con respaldo determinista
  en caso de que el binario no esté presente.
- **Base de ingredientes:** 68 registros científicos documentados y revisados (58 verificados y 10 ingredientes
  botánicos locales con datos insuficientes bajo la Regla 6.2), referenciando fuentes oficiales (ECHA, PubChem, CosIng, US EPA).

### Trabajo futuro

Queda como trabajo futuro fuera del alcance de este prototipo:
1. Entrenamiento y fine-tuning de modelos contextuales densos (BETO / RoBERTa biomédico).
2. Modelos de secuencia (BiLSTM-CRF) para reconocimiento de entidades nombradas (NER) orientado a detectar claims publicitarios y greenwashing.
3. Métodos de explicabilidad local de modelos de caja negra (LIME / SHAP) sobre clasificadores neuronales.
4. Conexión opcional a servicios comerciales de OCR (Google Cloud Vision / AWS Textract).

## Cómo correrlo localmente

```bash
# Requiere Python 3.12+ (ver .python-version) y uv o pip
uv sync   # o: pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

La base de datos SQLite (`yakuri.db`) se crea automáticamente en el primer arranque,
con los ingredientes semilla de `app/database.py`.

Para correr las pruebas:

```bash
pytest
```

## Despliegue

Desplegado en [Render](https://render.com) a partir de `render.yaml` (plan gratuito).
El primer request tras un período de inactividad puede tardar unos segundos por el
arranque en frío (cold start) característico del plan gratuito.

## Contexto académico

Proyecto desarrollado para el curso de Procesamiento del Lenguaje Natural de la
Maestría en Inteligencia Artificial, Universidad Continental (Perú), por
Angel Freedd Espinoza Julcarima.
