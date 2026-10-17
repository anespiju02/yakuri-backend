from pydantic import BaseModel, Field
from typing import List, Optional, Literal

EstadoIngrediente = Literal["verified", "insufficient_data"]
GradoImpactoHidrico = Literal["A", "B", "C", "D", "E", "N/A"]


class IngredienteDto(BaseModel):
    id: str = Field(..., examples=["ing_0001"])
    inci_name: str = Field(..., examples=["Sodium Laureth Sulfate"])
    synonyms: List[str] = Field(default_factory=list, examples=[["SLES", "sodium laureth sulphate"]])
    category: str = Field(..., examples=["tensioactivo"])
    water_impact_weight: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Peso de impacto hídrico (0 a 1). Null si status es insufficient_data (Regla 6.2)."
    )
    status: EstadoIngrediente = Field(default="verified")
    justification: str = Field(..., description="Justificación científica documentada para el RAG.")
    source: str = Field(..., examples=["ECHA", "US EPA", "CosIng"])
    source_url: str = Field(..., examples=["https://echa.europa.eu/"])
    last_reviewed: str = Field(..., examples=["2026-01-15"])


class CrearIngredienteRequest(BaseModel):
    inci_name: str
    synonyms: List[str] = []
    category: str
    water_impact_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: EstadoIngrediente = "verified"
    justification: str
    source: str
    source_url: str
    last_reviewed: str


class SolicitudEscaneoTexto(BaseModel):
    raw_ocr_text: str = Field(..., description="Texto crudo extraído de la etiqueta")
    product_name: Optional[str] = Field(default=None, description="Nombre descriptivo opcional")
    brand_ignored: Optional[str] = Field(
        default=None,
        description="Regla 6.1: Recibido solo para pruebas de invarianza, jamás entra al motor de cálculo."
    )
    price_pen_ignored: Optional[float] = Field(
        default=None,
        description="Regla 6.1: Precio en soles ignorado por el motor de puntaje."
    )


class ResultadoEscaneoDto(BaseModel):
    scan_id: str
    raw_ocr_text: str
    matched_ingredients: List[str]
    unmatched_text_fragments: List[str]
    insufficient_data_ingredients: List[str]
    water_impact_score: GradoImpactoHidrico
    score_numeric: Optional[float]
    explanation: str
    alternatives: List[str]
    timestamp: str
    traceability_details: List[IngredienteDto]


class EjecucionMarcaDto(BaseModel):
    brand_injected: str
    price_injected: float
    score_numeric: Optional[float]
    water_impact_score: GradoImpactoHidrico


class ResultadoProductoAuditoriaDto(BaseModel):
    product_type: str
    baseline_score: Optional[float]
    baseline_grade: GradoImpactoHidrico
    variance: float
    passed: bool
    brand_runs: List[EjecucionMarcaDto]


class ReporteSustitucionMarcaDto(BaseModel):
    consistency_rate_percent: float
    all_passed: bool
    total_products_tested: int
    results: List[ResultadoProductoAuditoriaDto]


class MetricasPrototipoDto(BaseModel):
    total_ingredientes: int
    ingredientes_verificados: int
    ingredientes_datos_insuficientes: int
    total_escaneos_registrados: int
    porcentaje_escaneos_con_indice_explicado: float
    consistencia_sustitucion_marca_pct: float
    cumple_criterio_exito_90_pct_explicados: bool
