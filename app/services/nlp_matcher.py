import logging
import re
from typing import Tuple, List, Optional
from rapidfuzz import fuzz
from app.models import IngredienteDto, MetodoMatching
from app.sqlite_repo import fetch_all_ingredients

logger = logging.getLogger("yakuri.nlp_matcher")

STOP_WORDS = {"aqua", "water", "agua", "agua purificada"}

# Estado del modelo de similitud semántica (Sentence Transformers)
SEMANTIC_MATCHING_AVAILABLE: bool = False
_model = None
_cached_embeddings = None
_cached_entries: List[Tuple[str, IngredienteDto]] = []


def normalize_token(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^(ingredientes|ingredients|composicion|contiene)\s*[:\-]?\s*", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9áéíóúñ\s\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def build_catalog_embeddings() -> None:
    """Precalcula y cachea en memoria los embeddings de inci_name + synonyms de todo el catálogo."""
    global _cached_embeddings, _cached_entries
    if not SEMANTIC_MATCHING_AVAILABLE or _model is None:
        return
    try:
        catalog = fetch_all_ingredients()
        entries: List[Tuple[str, IngredienteDto]] = []
        texts_to_embed: List[str] = []
        for ing in catalog:
            candidates = [ing.inci_name] + ing.synonyms
            for candidate in candidates:
                norm_cand = normalize_token(candidate)
                if norm_cand and norm_cand not in STOP_WORDS:
                    entries.append((norm_cand, ing))
                    texts_to_embed.append(norm_cand)
        if texts_to_embed:
            _cached_embeddings = _model.encode(texts_to_embed, convert_to_tensor=True)
            _cached_entries = entries
            logger.info(f"Embeddings calculados para {len(texts_to_embed)} variantes del catálogo.")
    except Exception as e:
        logger.warning(f"Error al precalcular embeddings del catálogo: {e}")


def init_semantic_model() -> bool:
    """
    Carga el modelo SentenceTransformer (paraphrase-multilingual-MiniLM-L12-v2) una sola vez al iniciar.
    Si falla (p.ej. falta de memoria en Render free tier), mantiene la app activa con fallback a rapidfuzz.
    """
    global SEMANTIC_MATCHING_AVAILABLE, _model
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Cargando modelo semántico paraphrase-multilingual-MiniLM-L12-v2...")
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        SEMANTIC_MATCHING_AVAILABLE = True
        build_catalog_embeddings()
        logger.info("Modelo semántico cargado y embeddings de catálogo inicializados.")
        return True
    except Exception as e:
        logger.warning(
            f"No se pudo cargar el modelo semántico SentenceTransformer ({e}). "
            "Continuando exclusivamente con matching difuso (rapidfuzz)."
        )
        SEMANTIC_MATCHING_AVAILABLE = False
        _model = None
        return False


def match_ingredients_from_ocr(
    raw_ocr_text: str,
    threshold: float = 82.0,
    semantic_threshold: float = 0.72
) -> Tuple[List[IngredienteDto], List[IngredienteDto], List[str], MetodoMatching]:
    """
    Estrategia de matching en dos pasadas (Prioridad 1):
    1. Primera pasada: coincidencia exacta y difusa con rapidfuzz (umbral >= 82.0).
    2. Segunda pasada (solo si rapidfuzz no alcanza el umbral): similitud semántica de embeddings.
    """
    catalog = fetch_all_ingredients()
    cleaned_block = re.sub(r"^(ingredientes|ingredients)\s*:\s*", "", raw_ocr_text, flags=re.IGNORECASE)
    raw_fragments = [frag.strip() for frag in re.split(r"[,;\n•·]+", cleaned_block) if frag.strip()]

    verified_matches: List[IngredienteDto] = []
    insufficient_matches: List[IngredienteDto] = []
    unmatched_fragments: List[str] = []
    seen_ids = set()
    used_semantic = False
    used_fuzzy = False

    for raw_frag in raw_fragments:
        norm_frag = normalize_token(raw_frag)
        if not norm_frag or norm_frag in STOP_WORDS:
            continue

        best_match: Optional[IngredienteDto] = None
        best_score = 0.0

        # Pasada 1: rapidfuzz (distancia de edición)
        for ing in catalog:
            for candidate in [ing.inci_name] + ing.synonyms:
                norm_cand = normalize_token(candidate)
                if not norm_cand:
                    continue
                if norm_frag == norm_cand:
                    score = 100.0
                elif len(norm_cand) >= 4 and re.search(rf"\b{re.escape(norm_cand)}\b", norm_frag):
                    score = 100.0
                else:
                    score = fuzz.ratio(norm_frag, norm_cand)

                if score > best_score:
                    best_score = score
                    best_match = ing

        if best_match and best_score >= threshold:
            used_fuzzy = True
            if best_match.id not in seen_ids:
                seen_ids.add(best_match.id)
                matched_ing = best_match.model_copy(update={"match_method": "fuzzy"})
                if matched_ing.status == "verified":
                    verified_matches.append(matched_ing)
                else:
                    insufficient_matches.append(matched_ing)
            continue

        # Pasada 2: similitud semántica con embeddings (solo si rapidfuzz no alcanzó el umbral)
        sem_matched = False
        if SEMANTIC_MATCHING_AVAILABLE and _model is not None and _cached_embeddings is not None and _cached_entries:
            try:
                from sentence_transformers import util
                frag_emb = _model.encode(norm_frag, convert_to_tensor=True)
                cos_scores = util.cos_sim(frag_emb, _cached_embeddings)[0]
                best_idx = int(cos_scores.argmax())
                best_sim = float(cos_scores[best_idx])
                if best_sim >= semantic_threshold:
                    _, sem_ing = _cached_entries[best_idx]
                    used_semantic = True
                    sem_matched = True
                    if sem_ing.id not in seen_ids:
                        seen_ids.add(sem_ing.id)
                        matched_ing = sem_ing.model_copy(update={"match_method": "semantico"})
                        if matched_ing.status == "verified":
                            verified_matches.append(matched_ing)
                        else:
                            insufficient_matches.append(matched_ing)
            except Exception as e:
                logger.warning(f"Error calculando similitud semántica para '{norm_frag}': {e}")

        if not sem_matched:
            unmatched_fragments.append(raw_frag)

    if used_fuzzy and used_semantic:
        matching_method: MetodoMatching = "hibrido_fuzzy_semantico"
    elif used_semantic:
        matching_method = "matching_semantico"
    else:
        matching_method = "matching_fuzzy"

    return verified_matches, insufficient_matches, unmatched_fragments, matching_method
