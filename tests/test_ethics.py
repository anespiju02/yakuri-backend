import io
from fastapi.testclient import TestClient
from app.main import app
from app.sqlite_repo import init_db
from app.services import nlp_matcher

init_db()
nlp_matcher.init_semantic_model()
client = TestClient(app)


def test_rule_6_1_commercial_independence():
    formula = "Ingredientes: Sodium Laureth Sulfate, Cocamidopropyl Betaine, Citric Acid"
    res_a = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": formula,
        "brand_ignored": "Marca Patrocinadora A",
        "price_pen_ignored": 99.90
    }).json()

    res_b = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": formula,
        "brand_ignored": "Marca Pequeña B",
        "price_pen_ignored": 4.50
    }).json()

    assert res_a["score_numeric"] == res_b["score_numeric"]
    assert res_a["water_impact_score"] == res_b["water_impact_score"]


def test_rule_6_2_insufficient_data_handling():
    formula = "Ingredientes: Decyl Glucoside, Citric Acid, Goma de Tara"
    res = client.post("/api/v1/escaneos/texto", json={"raw_ocr_text": formula}).json()

    assert res["score_numeric"] == 0.10
    assert res["water_impact_score"] == "A"
    assert "ing_0099" in res["insufficient_data_ingredients"]
    assert "ing_0099" not in res["matched_ingredients"]


def test_rule_6_3_brand_substitution_suite():
    res = client.post("/api/v1/auditorias-eticas/sustitucion-marca").json()
    assert res["all_passed"] is True
    assert res["consistency_rate_percent"] == 100.0


def test_semantic_matching_layer_resolves_descriptive_synonym():
    """
    Sección 1.6: Demuestra el valor agregado de la similitud semántica.
    'microesferas de plastico para exfoliacion' no comparte substring ni supera
    el umbral de 82.0 de rapidfuzz con 'Polyethylene' o 'microplastics',
    pero es resuelto por embeddings cosenoidales con origen 'semantico'.
    """
    formula = "Ingredientes: microesferas de plastico para exfoliacion"
    res = client.post("/api/v1/escaneos/texto", json={"raw_ocr_text": formula}).json()

    assert "ing_0047" in res["matched_ingredients"]
    assert res["matching_method"] == "matching_semantico"
    assert res["traceability_details"][0]["match_method"] == "semantico"
    assert res["water_impact_score"] == "E"  # Polyethylene tiene peso 0.98 -> Grado E


def test_transparency_generation_and_ocr_methods():
    """
    Sección 3: Verifica la transparencia auditable de generación y origen de OCR.
    """
    # 1. Escaneo por texto directo
    res_text = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: Sodium Laureth Sulfate"
    }).json()
    assert res_text["generation_method"] == "plantilla_grounded"
    assert res_text["ocr_method"] == "texto_directo"
    assert res_text["matching_method"] == "matching_fuzzy"

    # 2. Escaneo por imagen (declara modelo_ocr_fallback o modelo_ocr_real)
    fake_image = io.BytesIO(b"fake image bytes")
    res_img = client.post(
        "/api/v1/escaneos/imagen",
        files={"archivo": ("eco_detergente.jpg", fake_image, "image/jpeg")}
    ).json()
    assert res_img["generation_method"] == "plantilla_grounded"
    assert res_img["ocr_method"] in ["modelo_ocr_real", "modelo_ocr_fallback"]


def test_semantic_matching_fallback_when_unavailable(monkeypatch):
    """
    Sección 1.5: Si el modelo de embeddings no está disponible (ej. memoria en Render free tier),
    la app continúa operando exclusivamente con rapidfuzz sin romperse.
    """
    monkeypatch.setattr(nlp_matcher, "SEMANTIC_MATCHING_AVAILABLE", False)

    # Coincidencia fuzzy estándar sigue funcionando
    res = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: Sodium Laureth Sulfate"
    }).json()
    assert "ing_0001" in res["matched_ingredients"]
    assert res["matching_method"] == "matching_fuzzy"

    # El término puramente descriptivo que requería embeddings va a unmatched sin romper la app
    res_sem = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: microesferas de plastico para exfoliacion"
    }).json()
    assert "microesferas de plastico para exfoliacion" in res_sem["unmatched_text_fragments"]


def test_llm_grounded_generation_success(monkeypatch):
    """
    Sección 4.6 (a): Con el LLM mockeado devolviendo un texto válido sin alucinaciones,
    confirmar que se utiliza y se declara generation_method = 'llm_grounded'.
    """
    from app.services import rag_explainer

    simulated_llm_response = (
        "Este producto obtiene calificación B debido a la presencia de Sodium Laureth Sulfate. "
        "Dicho tensioactivo es biodegradable pero puede afectar organismos acuáticos en concentraciones altas."
    )
    monkeypatch.setattr(rag_explainer, "call_gemini_llm", lambda prompt: simulated_llm_response)

    res = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: Sodium Laureth Sulfate"
    }).json()

    assert res["generation_method"] == "llm_grounded"
    assert res["explanation"] == simulated_llm_response


def test_llm_generation_fallback_on_failure(monkeypatch):
    """
    Sección 4.6 (b): Con la llamada al LLM fallando (error de red/cuota/timeout),
    confirmar que cae automáticamente al respaldo determinista sin romper el endpoint.
    """
    from app.services import rag_explainer

    # Simular fallo en llamada a Gemini
    monkeypatch.setattr(rag_explainer, "call_gemini_llm", lambda prompt: None)

    res = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: Sodium Laureth Sulfate"
    }).json()

    assert res["generation_method"] == "plantilla_grounded"
    assert "Sodium Laureth Sulfate" in res["explanation"]
    assert res["water_impact_score"] is not None


def test_llm_hallucination_rejected_and_fallback_used(monkeypatch):
    """
    Sección 4.6 (c): Con el LLM mockeado alucinando un ingrediente que no pertenece a la fórmula,
    confirmar que la validación posterior lo detecta, lo rechaza y activa el respaldo determinista.
    """
    from app.services import rag_explainer

    # La fórmula solo contiene Citric Acid, pero el LLM alucina Triclosan
    hallucinated_response = (
        "Este producto contiene Triclosan altamente tóxico para la fauna acuática y Citric Acid."
    )
    monkeypatch.setattr(rag_explainer, "call_gemini_llm", lambda prompt: hallucinated_response)

    res = client.post("/api/v1/escaneos/texto", json={
        "raw_ocr_text": "Ingredientes: Citric Acid"
    }).json()

    # Debe ser rechazado por la salvaguarda de alucinación y usar plantilla grounded
    assert res["generation_method"] == "plantilla_grounded"
    assert "Triclosan" not in res["explanation"]
    assert "Citric Acid" in res["explanation"]

