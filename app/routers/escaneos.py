import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models import SolicitudEscaneoTexto, ResultadoEscaneoDto, IngredienteDto
from app.services.nlp_matcher import match_ingredients_from_ocr
from app.services.scoring import calculate_water_impact, suggest_alternatives
from app.services.rag_explainer import generate_explanation
from app.services.ocr_service import extract_text_from_image_bytes
from app.sqlite_repo import save_product_scan, fetch_recent_scans, fetch_scan_by_id

router = APIRouter(prefix="/api/v1/escaneos", tags=["Escaneos"])


@router.post(
    "/texto",
    response_model=ResultadoEscaneoDto,
    operation_id="escanearEtiquetaTexto",
    summary="Analiza texto de etiqueta (PLN + Motor A-E + Explicación RAG)"
)
def escanear_etiqueta_texto(payload: SolicitudEscaneoTexto) -> ResultadoEscaneoDto:
    return procesar_escaneo(payload, ocr_method="texto_directo")


def procesar_escaneo(
    payload: SolicitudEscaneoTexto,
    ocr_method: str = "texto_directo"
) -> ResultadoEscaneoDto:
    verified, insufficient, unmatched, matching_method = match_ingredients_from_ocr(payload.raw_ocr_text)

    # Regla 6.1: brand_ignored y price_pen_ignored jamás entran al motor
    score_numeric, grade = calculate_water_impact(verified)

    explanation, generation_method = generate_explanation(
        verified_ingredients=verified,
        insufficient_ingredients=insufficient,
        grade=grade,
        score_numeric=score_numeric,
    )

    traceability = [
        IngredienteDto(**ing.model_dump())
        for ing in (verified + insufficient)
    ]

    result = ResultadoEscaneoDto(
        scan_id=f"scan_{uuid.uuid4().hex[:8]}",
        raw_ocr_text=payload.raw_ocr_text,
        matched_ingredients=[i.id for i in verified],
        unmatched_text_fragments=unmatched,
        insufficient_data_ingredients=[i.id for i in insufficient],
        water_impact_score=grade,
        score_numeric=score_numeric,
        explanation=explanation,
        alternatives=suggest_alternatives(grade),
        timestamp=datetime.now(timezone.utc).isoformat(),
        traceability_details=traceability,
        generation_method=generation_method,
        ocr_method=ocr_method,  # type: ignore
        matching_method=matching_method,
    )
    save_product_scan(result)
    return result


@router.post(
    "/imagen",
    response_model=ResultadoEscaneoDto,
    operation_id="escanearEtiquetaImagen",
    summary="Fase 3: Extrae texto vía OCR desde foto de etiqueta y calcula impacto A-E"
)
async def escanear_etiqueta_imagen(
    archivo: UploadFile=File(..., description="Fotografía de la etiqueta"),
    brand_ignored: Optional[str]=Form(None),
    price_pen_ignored: Optional[float]=Form(None),
) -> ResultadoEscaneoDto:
    image_bytes = await archivo.read()
    raw_text, ocr_method = extract_text_from_image_bytes(image_bytes, archivo.filename or "")
    return procesar_escaneo(
        SolicitudEscaneoTexto(
            raw_ocr_text=raw_text,
            brand_ignored=brand_ignored,
            price_pen_ignored=price_pen_ignored,
        ),
        ocr_method=ocr_method,
    )


@router.get(
    "",
    response_model=List[ResultadoEscaneoDto],
    operation_id="listarHistorialEscaneos",
    summary="Lista los escaneos almacenados en SQLite (Tabla products - Sección 4.2)"
)
def listar_historial_escaneos(limite: int=20):
    return fetch_recent_scans(limit=limite)


@router.get(
    "/{scan_id}",
    response_model=ResultadoEscaneoDto,
    operation_id="obtenerEscaneoPorId",
    summary="Recupera un escaneo específico por su ID"
)
def obtener_escaneo_por_id(scan_id: str):
    scan = fetch_scan_by_id(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Escaneo no encontrado")
    return scan
