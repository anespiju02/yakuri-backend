import logging
import os
import re
from typing import List, Optional, Tuple
from app.models import IngredienteDto, MetodoGeneracion
from app.sqlite_repo import fetch_all_ingredients

logger = logging.getLogger("yakuri.rag_explainer")

YAKURI_SYSTEM_PROMPT = """Eres el redactor de explicaciones de Yakuri. Recibes una lista de ingredientes
identificados, su peso de impacto hídrico y su justificación documentada.
Redacta una explicación breve (máx. 3 oraciones) en español claro, dirigida a
un consumidor sin formación técnica, basada ÚNICAMENTE en los datos recibidos.
No uses ningún dato, cifra o afirmación que no esté en la justificación provista.
Si la evidencia es insuficiente para algún ingrediente, indícalo explícitamente
en vez de omitirlo o inventar una explicación."""


def generate_grounded_explanation(
    verified_ingredients: List[IngredienteDto],
    insufficient_ingredients: List[IngredienteDto],
    grade: str,
    score_numeric: Optional[float]
) -> str:
    """
    Generador determinista RAG-restringido basado en plantillas (100% libre de alucinaciones).
    Utiliza exclusivamente los campos `justification` y `source` de los ingredientes detectados.
    Actúa como respaldo obligatorio (safety net) si el LLM no está disponible o falla la validación.
    """
    if not verified_ingredients and not insufficient_ingredients:
        return (
            "No se identificaron ingredientes registrados en nuestra base científica a partir del texto analizado. "
            "Por transparencia ética, Yakuri no emite una calificación cuando carece de evidencia verificada."
        )

    sentences: List[str] = []

    # Oración 1: Calificación general y principal impulsor verificado
    if verified_ingredients and score_numeric is not None:
        sorted_verified = sorted(
            verified_ingredients,
            key=lambda x: x.water_impact_weight or 0.0,
            reverse=True
        )
        top = sorted_verified[0]
        sentences.append(
            f"Este producto obtiene una calificación {grade} (índice {score_numeric:.2f}) "
            f"principalmente por contener {top.inci_name} ({top.source}): {top.justification.lower()}"
        )

        # Oración 2: Otros ingredientes verificados presentes
        if len(sorted_verified) > 1:
            second = sorted_verified[1]
            sentences.append(
                f"También incluye {second.inci_name} ({second.source}), el cual es {second.justification[0].lower() + second.justification[1:]}"
            )

    # Oración 3 (o 2): Declaración explícita de datos insuficientes (Regla 5 y 6.2)
    if insufficient_ingredients:
        names = ", ".join(ing.inci_name for ing in insufficient_ingredients)
        sentences.append(
            f"No se encontró evidencia suficiente sobre {names}, por lo que se excluyó del cálculo numérico para no penalizar injustamente la fórmula."
        )

    # Garantizar máximo 3 oraciones según Sección 5
    return " ".join(sentences[:3])


def _build_gemini_prompt(
    verified_ingredients: List[IngredienteDto],
    insufficient_ingredients: List[IngredienteDto],
    grade: str,
    score_numeric: Optional[float]
) -> str:
    """Construye el prompt estrictamente restringido (grounded) para Gemini."""
    lines = [
        YAKURI_SYSTEM_PROMPT,
        "",
        "--- CONTEXTO CIENTÍFICO PROVISTO ---",
        f"Calificación asignada por el motor de cálculo: Grado {grade}" + (f" (Índice numérico: {score_numeric:.2f})" if score_numeric is not None else ""),
        "",
        "Ingredientes verificados en este producto:"
    ]

    if verified_ingredients:
        for ing in verified_ingredients:
            lines.append(
                f"- {ing.inci_name} (Categoría: {ing.category}, Peso de impacto hídrico: {ing.water_impact_weight}, Fuente: {ing.source}): {ing.justification}"
            )
    else:
        lines.append("- Ninguno verificado en el catálogo.")

    lines.append("")
    lines.append("Ingredientes con datos insuficientes (excluidos del cálculo numérico por la Regla 6.2):")
    if insufficient_ingredients:
        for ing in insufficient_ingredients:
            lines.append(f"- {ing.inci_name}: {ing.justification}")
    else:
        lines.append("- Ninguno.")

    lines.append("")
    lines.append("INSTRUCCIÓN FINAL: Redacta la explicación final (máximo 3 oraciones). NO agregues ingredientes ni menciones marcas ni precios.")
    return "\n".join(lines)


def call_gemini_llm(prompt: str) -> Optional[str]:
    """
    Invoca la API de Gemini usando el SDK oficial google-genai.
    Si la API key no está configurada o la llamada falla, retorna None.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key.strip().startswith("tu_"):
        return None

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=350,
            )
        )
        if response and response.text:
            text = response.text.strip()
            if text:
                return text
    except Exception as e:
        logger.warning(f"Fallo en llamada a Gemini API ({e}). Se activará el respaldo determinista.")

    return None


def validate_llm_output(
    llm_text: str,
    verified_ingredients: List[IngredienteDto],
    insufficient_ingredients: List[IngredienteDto]
) -> bool:
    """
    Salvaguarda XAI (Sección 4.4):
    Verifica que el texto generado por el LLM no mencione ningún inci_name que NO pertenezca
    a la fórmula analizada (prevención estricta de alucinaciones).
    """
    if not llm_text or len(llm_text.strip()) < 15:
        return False

    valid_inci_names = {
        ing.inci_name.lower().strip()
        for ing in (verified_ingredients + insufficient_ingredients)
    }

    try:
        catalog = fetch_all_ingredients()
        prohibited_inci = [
            ing.inci_name.lower().strip()
            for ing in catalog
            if ing.inci_name.lower().strip() not in valid_inci_names
        ]

        llm_lower = llm_text.lower()
        for prohibited in prohibited_inci:
            # Detección por límite de palabra para no dar falsos positivos
            if re.search(rf"\b{re.escape(prohibited)}\b", llm_lower):
                logger.warning(
                    f"Alucinación detectada: el LLM mencionó '{prohibited}', que no está "
                    f"en la lista analizada. Rechazando salida del LLM."
                )
                return False
    except Exception as e:
        logger.warning(f"Error durante validación de alucinaciones del LLM: {e}")
        return False

    return True


def generate_explanation(
    verified_ingredients: List[IngredienteDto],
    insufficient_ingredients: List[IngredienteDto],
    grade: str,
    score_numeric: Optional[float]
) -> Tuple[str, MetodoGeneracion]:
    """
    Flujo principal de generación de explicaciones (Prioridad 4):
    1. Si no hay ingredientes, retorna directamente la explicación estándar de transparencia.
    2. Intenta generar con Gemini LLM usando grounded prompt.
    3. Valida que la respuesta del LLM no tenga alucinaciones (no mencione ingredientes ausentes).
    4. Si el LLM tiene éxito y pasa la validación, retorna (texto, "llm_grounded").
    5. Si falla la API o la validación, activa automáticamente el respaldo determinista (texto, "plantilla_grounded").
    """
    if not verified_ingredients and not insufficient_ingredients:
        return generate_grounded_explanation(
            verified_ingredients, insufficient_ingredients, grade, score_numeric
        ), "plantilla_grounded"

    # Intentar con el LLM real
    prompt = _build_gemini_prompt(verified_ingredients, insufficient_ingredients, grade, score_numeric)
    llm_output = call_gemini_llm(prompt)

    if llm_output and validate_llm_output(llm_output, verified_ingredients, insufficient_ingredients):
        return llm_output, "llm_grounded"

    # Respaldo determinista garantizado (cero alucinaciones)
    fallback_text = generate_grounded_explanation(
        verified_ingredients, insufficient_ingredients, grade, score_numeric
    )
    return fallback_text, "plantilla_grounded"
