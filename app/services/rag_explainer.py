from typing import List, Optional
from app.models import IngredienteDto

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
    Generador determinista RAG-restringido (100% libre de alucinaciones para el PMV).
    Utiliza exclusivamente los campos `justification` y `source` de los ingredientes detectados.
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
