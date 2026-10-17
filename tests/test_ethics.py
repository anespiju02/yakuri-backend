from fastapi.testclient import TestClient
from app.main import app
from app.sqlite_repo import init_db

init_db()
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
