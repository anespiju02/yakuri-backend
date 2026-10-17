from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.models import IngredienteDto, CrearIngredienteRequest, EstadoIngrediente
from app.sqlite_repo import fetch_all_ingredients, fetch_ingredient_by_id, insert_ingredient

router = APIRouter(prefix="/api/v1/ingredientes", tags=["Ingredientes"])


@router.get(
    "",
    response_model=List[IngredienteDto],
    operation_id="listarIngredientes",
    summary="Lista y filtra la base científica de ingredientes (Sección 4.1)"
)
def listar_ingredientes(
    estado: Optional[EstadoIngrediente]=Query(None, description="Filtrar por verified o insufficient_data"),
    busqueda: Optional[str]=Query(None, description="Buscar por nombre INCI, sinónimo o categoría")
):
    items = fetch_all_ingredients()
    if estado:
        items = [i for i in items if i.status == estado]
    if busqueda:
        q = busqueda.lower().strip()
        items = [
            i for i in items
            if q in i.inci_name.lower()
            or q in i.category.lower()
            or any(q in syn.lower() for syn in i.synonyms)
        ]
    return items


@router.get(
    "/{ingrediente_id}",
    response_model=IngredienteDto,
    operation_id="obtenerIngredientePorId",
    summary="Obtiene el detalle y trazabilidad de un ingrediente específico"
)
def obtener_ingrediente(ingrediente_id: str):
    ing = fetch_ingredient_by_id(ingrediente_id)
    if not ing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    return ing


@router.post(
    "",
    response_model=IngredienteDto,
    status_code=status.HTTP_201_CREATED,
    operation_id="registrarIngrediente",
    summary="Registra un nuevo ingrediente respetando la Regla 6.2"
)
def registrar_ingrediente(payload: CrearIngredienteRequest):
    # Regla 6.2: Si el estado es insufficient_data, forzamos water_impact_weight = None
    peso = None if payload.status == "insufficient_data" else payload.water_impact_weight
    return insert_ingredient(payload, peso)
