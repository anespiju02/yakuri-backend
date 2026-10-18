import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from app.models import (
    IngredienteDto,
    CrearIngredienteRequest,
    ResultadoEscaneoDto,
)
from app.database import INGREDIENTS_DB

DB_PATH = Path(__file__).resolve().parent.parent / "yakuri.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_ingredient(row: sqlite3.Row) -> IngredienteDto:
    return IngredienteDto(
        id=row["id"],
        inci_name=row["inci_name"],
        synonyms=json.loads(row["synonyms_json"]),
        category=row["category"],
        water_impact_weight=row["water_impact_weight"],
        status=row["status"],
        justification=row["justification"],
        source=row["source"],
        source_url=row["source_url"],
        last_reviewed=row["last_reviewed"],
    )


def init_db() -> None:
    """Inicializa las tablas ingredients (Sección 4.1) y products (Sección 4.2) en SQLite."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id TEXT PRIMARY KEY,
                inci_name TEXT NOT NULL,
                synonyms_json TEXT NOT NULL,
                category TEXT NOT NULL,
                water_impact_weight REAL NULL,
                status TEXT NOT NULL,
                justification TEXT NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                last_reviewed TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                scan_id TEXT PRIMARY KEY,
                raw_ocr_text TEXT NOT NULL,
                matched_ingredients_json TEXT NOT NULL,
                unmatched_text_fragments_json TEXT NOT NULL,
                insufficient_data_ingredients_json TEXT NOT NULL,
                water_impact_score TEXT NOT NULL,
                score_numeric REAL NULL,
                explanation TEXT NOT NULL,
                alternatives_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                generation_method TEXT DEFAULT 'plantilla_grounded',
                ocr_method TEXT DEFAULT 'texto_directo',
                matching_method TEXT DEFAULT 'matching_fuzzy'
            )
        """)

        # Migración dinámica de columnas en products si la BD ya existía
        cursor = conn.execute("PRAGMA table_info(products)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "generation_method" not in existing_cols:
            conn.execute("ALTER TABLE products ADD COLUMN generation_method TEXT DEFAULT 'plantilla_grounded'")
        if "ocr_method" not in existing_cols:
            conn.execute("ALTER TABLE products ADD COLUMN ocr_method TEXT DEFAULT 'texto_directo'")
        if "matching_method" not in existing_cols:
            conn.execute("ALTER TABLE products ADD COLUMN matching_method TEXT DEFAULT 'matching_fuzzy'")

        # Cargar o actualizar el catálogo completo de ingredientes semilla
        for ing in INGREDIENTS_DB:
            conn.execute(
                """
                INSERT OR REPLACE INTO ingredients (
                    id, inci_name, synonyms_json, category,
                    water_impact_weight, status, justification,
                    source, source_url, last_reviewed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ing.id,
                    ing.inci_name,
                    json.dumps(ing.synonyms, ensure_ascii=False),
                    ing.category,
                    ing.water_impact_weight,
                    ing.status,
                    ing.justification,
                    ing.source,
                    ing.source_url,
                    ing.last_reviewed,
                ),
            )
        conn.commit()


def fetch_all_ingredients() -> List[IngredienteDto]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM ingredients ORDER BY id ASC").fetchall()
        return [_row_to_ingredient(r) for r in rows]


def fetch_ingredient_by_id(ingrediente_id: str) -> Optional[IngredienteDto]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ingredients WHERE id = ?", (ingrediente_id,)
        ).fetchone()
        return _row_to_ingredient(row) if row else None


def insert_ingredient(
    payload: CrearIngredienteRequest, validated_weight: Optional[float]
) -> IngredienteDto:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
        new_id = f"ing_{total + 101:04d}"
        conn.execute(
            """
            INSERT INTO ingredients (
                id, inci_name, synonyms_json, category,
                water_impact_weight, status, justification,
                source, source_url, last_reviewed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                payload.inci_name,
                json.dumps(payload.synonyms, ensure_ascii=False),
                payload.category,
                validated_weight,
                payload.status,
                payload.justification,
                payload.source,
                payload.source_url,
                payload.last_reviewed,
            ),
        )
        conn.commit()

    return IngredienteDto(
        id=new_id,
        inci_name=payload.inci_name,
        synonyms=payload.synonyms,
        category=payload.category,
        water_impact_weight=validated_weight,
        status=payload.status,
        justification=payload.justification,
        source=payload.source,
        source_url=payload.source_url,
        last_reviewed=payload.last_reviewed,
    )


def save_product_scan(scan: ResultadoEscaneoDto) -> None:
    """Almacena el escaneo en la tabla products sin guardar marca ni precio (Regla 6.1)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO products (
                scan_id, raw_ocr_text, matched_ingredients_json,
                unmatched_text_fragments_json, insufficient_data_ingredients_json,
                water_impact_score, score_numeric, explanation,
                alternatives_json, timestamp,
                generation_method, ocr_method, matching_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan.scan_id,
                scan.raw_ocr_text,
                json.dumps(scan.matched_ingredients, ensure_ascii=False),
                json.dumps(scan.unmatched_text_fragments, ensure_ascii=False),
                json.dumps(scan.insufficient_data_ingredients, ensure_ascii=False),
                scan.water_impact_score,
                scan.score_numeric,
                scan.explanation,
                json.dumps(scan.alternatives, ensure_ascii=False),
                scan.timestamp,
                scan.generation_method,
                scan.ocr_method,
                scan.matching_method,
            ),
        )
        conn.commit()


def _row_to_scan_dto(
    row: sqlite3.Row, ingredients_map: dict[str, IngredienteDto]
) -> ResultadoEscaneoDto:
    matched_ids: List[str] = json.loads(row["matched_ingredients_json"])
    insufficient_ids: List[str] = json.loads(row["insufficient_data_ingredients_json"])
    all_ids = matched_ids + insufficient_ids

    traceability = [
        ingredients_map[ing_id]
        for ing_id in all_ids
        if ing_id in ingredients_map
    ]

    keys = row.keys()
    gen_method = row["generation_method"] if "generation_method" in keys and row["generation_method"] else "plantilla_grounded"
    ocr_m = row["ocr_method"] if "ocr_method" in keys and row["ocr_method"] else "texto_directo"
    mat_m = row["matching_method"] if "matching_method" in keys and row["matching_method"] else "matching_fuzzy"

    return ResultadoEscaneoDto(
        scan_id=row["scan_id"],
        raw_ocr_text=row["raw_ocr_text"],
        matched_ingredients=matched_ids,
        unmatched_text_fragments=json.loads(row["unmatched_text_fragments_json"]),
        insufficient_data_ingredients=insufficient_ids,
        water_impact_score=row["water_impact_score"],
        score_numeric=row["score_numeric"],
        explanation=row["explanation"],
        alternatives=json.loads(row["alternatives_json"]),
        timestamp=row["timestamp"],
        traceability_details=traceability,
        generation_method=gen_method,
        ocr_method=ocr_m,
        matching_method=mat_m,
    )


def fetch_recent_scans(limit: int=20) -> List[ResultadoEscaneoDto]:
    ingredients_map = {ing.id: ing for ing in fetch_all_ingredients()}
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_scan_dto(r, ingredients_map) for r in rows]


def fetch_scan_by_id(scan_id: str) -> Optional[ResultadoEscaneoDto]:
    ingredients_map = {ing.id: ing for ing in fetch_all_ingredients()}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        return _row_to_scan_dto(row, ingredients_map) if row else None
