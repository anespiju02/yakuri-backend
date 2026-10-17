from app.models import IngredienteDto
from typing import List, Tuple, Optional, Literal

ScoreGrade = Literal["A", "B", "C", "D", "E", "N/A"]


def calculate_water_impact(ingredients: List[IngredienteDto]) -> Tuple[Optional[float], ScoreGrade]:
    """
    Sección 4.3 y Reglas Éticas 6.1 / 6.2:
    - Excluye ingredientes con status 'insufficient_data' sin asignar peso por defecto.
    - No recibe marca, precio ni variables comerciales.
    """
    valid_weights = [
        ing.water_impact_weight
        for ing in ingredients
        if ing.status == "verified" and ing.water_impact_weight is not None
    ]

    if not valid_weights:
        return None, "N/A"

    score_numeric = round(sum(valid_weights) / len(valid_weights), 2)

    if score_numeric <= 0.20:
        grade: ScoreGrade = "A"
    elif score_numeric <= 0.40:
        grade = "B"
    elif score_numeric <= 0.60:
        grade = "C"
    elif score_numeric <= 0.80:
        grade = "D"
    else:
        grade = "E"

    return score_numeric, grade


def suggest_alternatives(grade: ScoreGrade) -> List[str]:
    if grade in ("A", "B"):
        return ["Este producto ya se encuentra en el rango de bajo impacto hídrico (A-B)."]
    return [
        "Fórmulas con tensioactivos glucosídicos (Decyl Glucoside) y reguladores biodegradables (Citric Acid).",
        "Detergentes y limpiadores libres de fosfatos (STPP), agentes quelantes persistentes (EDTA) y Triclosán."
    ]
