import re
from typing import Tuple, List
from rapidfuzz import fuzz
from app.models import IngredienteDto
from app.sqlite_repo import fetch_all_ingredients

STOP_WORDS = {"aqua", "water", "agua", "agua purificada"}


def normalize_token(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^(ingredientes|ingredients|composicion|contiene)\s*[:\-]?\s*", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9áéíóúñ\s\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def match_ingredients_from_ocr(
    raw_ocr_text: str, threshold: float=82.0
) -> Tuple[List[IngredienteDto], List[IngredienteDto], List[str]]:
    catalog = fetch_all_ingredients()
    cleaned_block = re.sub(r"^(ingredientes|ingredients)\s*:\s*", "", raw_ocr_text, flags=re.IGNORECASE)
    raw_fragments = [frag.strip() for frag in re.split(r"[,;\n•·]+", cleaned_block) if frag.strip()]

    verified_matches: List[IngredienteDto] = []
    insufficient_matches: List[IngredienteDto] = []
    unmatched_fragments: List[str] = []
    seen_ids = set()

    for raw_frag in raw_fragments:
        norm_frag = normalize_token(raw_frag)
        if not norm_frag or norm_frag in STOP_WORDS:
            continue

        best_match: IngredienteDto | None = None
        best_score = 0.0

        for ing in catalog:
            for candidate in [ing.inci_name] + ing.synonyms:
                norm_cand = normalize_token(candidate)
                if norm_frag == norm_cand or norm_cand in norm_frag:
                    score = 100.0
                else:
                    score = fuzz.ratio(norm_frag, norm_cand)

                if score > best_score:
                    best_score = score
                    best_match = ing

        if best_match and best_score >= threshold:
            if best_match.id not in seen_ids:
                seen_ids.add(best_match.id)
                if best_match.status == "verified":
                    verified_matches.append(best_match)
                else:
                    insufficient_matches.append(best_match)
        else:
            unmatched_fragments.append(raw_frag)

    return verified_matches, insufficient_matches, unmatched_fragments
