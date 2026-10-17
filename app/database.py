from typing import List
from app.models import IngredienteDto

INGREDIENTS_DB: List[IngredienteDto] = [
    IngredienteDto(
        id="ing_0001",
        inci_name="Sodium Laureth Sulfate",
        synonyms=["SLES", "sodium laureth sulphate", "lauril eter sulfato de sodio"],
        category="tensioactivo",
        water_impact_weight=0.60,
        status="verified",
        justification="Biodegradable pero puede afectar organismos acuáticos en concentraciones altas.",
        source="ECHA",
        source_url="https://echa.europa.eu/substance-information/-/substanceinfo/100.105.627",
        last_reviewed="2026-01-15"
    ),
    IngredienteDto(
        id="ing_0002",
        inci_name="Triclosan",
        synonyms=["5-chloro-2-(2,4-dichlorophenoxy)phenol", "irgasan"],
        category="antibacteriano",
        water_impact_weight=0.95,
        status="verified",
        justification="Altamente tóxico para algas y fauna acuática con potencial de bioacumulación.",
        source="US EPA",
        source_url="https://comptox.epa.gov/dashboard/chemical/details/DTXSID5021388",
        last_reviewed="2026-01-20"
    ),
    IngredienteDto(
        id="ing_0003",
        inci_name="Cocamidopropyl Betaine",
        synonyms=["CAPB", "cocamidopropil betaina"],
        category="tensioactivo",
        water_impact_weight=0.35,
        status="verified",
        justification="Tensioactivo anfótero con toxicidad acuática moderada-baja y rápida degradación.",
        source="CosIng",
        source_url="https://ec.europa.eu/growth/tools-databases/cosing/",
        last_reviewed="2026-02-02"
    ),
    IngredienteDto(
        id="ing_0004",
        inci_name="Sodium Tripolyphosphate",
        synonyms=["STPP", "tripolifosfato de sodio", "pentasodium triphosphate"],
        category="secuestrante / fosfato",
        water_impact_weight=0.88,
        status="verified",
        justification="Promueve la eutrofización severa en cuerpos de agua dulce y proliferación de microalgas.",
        source="US EPA",
        source_url="https://comptox.epa.gov/dashboard/",
        last_reviewed="2026-01-18"
    ),
    IngredienteDto(
        id="ing_0005",
        inci_name="Decyl Glucoside",
        synonyms=["decil glucosido", "alquil poliglucosido"],
        category="tensioactivo no iónico",
        water_impact_weight=0.12,
        status="verified",
        justification="Derivado vegetal fácilmente biodegradable en ambientes aerobios y anaerobios con mínima ecotoxicidad.",
        source="ECHA",
        source_url="https://echa.europa.eu/",
        last_reviewed="2026-02-10"
    ),
    IngredienteDto(
        id="ing_0006",
        inci_name="Citric Acid",
        synonyms=["acido citrico", "citrate"],
        category="regulador de pH",
        water_impact_weight=0.08,
        status="verified",
        justification="Se degrada rápidamente en estaciones de tratamiento y cuerpos de agua sin efectos bioacumulativos.",
        source="CosIng",
        source_url="https://ec.europa.eu/growth/tools-databases/cosing/",
        last_reviewed="2026-02-05"
    ),
    IngredienteDto(
        id="ing_0007",
        inci_name="Linear Alkylbenzene Sulfonate",
        synonyms=["LAS", "sulfonato de alquilbenceno lineal", "sodium dodecylbenzenesulfonate"],
        category="tensioactivo aniónico",
        water_impact_weight=0.68,
        status="verified",
        justification="Presenta toxicidad aguda para peces e invertebrados antes de su biodegradación aerobia completa.",
        source="ECHA",
        source_url="https://echa.europa.eu/",
        last_reviewed="2026-01-25"
    ),
    IngredienteDto(
        id="ing_0008",
        inci_name="Sodium Hypochlorite",
        synonyms=["hipoclorito de sodio", "lejia", "cloro activo"],
        category="desinfectante / blanqueador",
        water_impact_weight=0.85,
        status="verified",
        justification="Altamente reactivo y tóxico para organismos acuáticos; puede formar subproductos organoclorados persistentes.",
        source="US EPA",
        source_url="https://comptox.epa.gov/dashboard/",
        last_reviewed="2026-01-30"
    ),
    IngredienteDto(
        id="ing_0009",
        inci_name="Glycerin",
        synonyms=["glicerina", "glicerol", "vegetable glycerin"],
        category="humectante",
        water_impact_weight=0.05,
        status="verified",
        justification="Compuesto orgánico inocuo para la vida acuática y completamente biodegradable.",
        source="CosIng",
        source_url="https://ec.europa.eu/growth/tools-databases/cosing/",
        last_reviewed="2026-02-11"
    ),
    IngredienteDto(
        id="ing_0010",
        inci_name="EDTA Tetrasodium",
        synonyms=["tetrasodium edta", "edta", "acido etilendiaminotetraacetico"],
        category="quelante",
        water_impact_weight=0.74,
        status="verified",
        justification="Baja biodegradabilidad; puede movilizar metales pesados desde sedimentos fluviales.",
        source="ECHA",
        source_url="https://echa.europa.eu/",
        last_reviewed="2026-02-01"
    ),
    # Regla 6.2: Ingredientes locales con insufficient_data y peso None
    IngredienteDto(
        id="ing_0099",
        inci_name="Caesalpinia Spinosa Gum",
        synonyms=["goma de tara", "extracto de tara andina", "tara gum"],
        category="espesante botánico local",
        water_impact_weight=None,
        status="insufficient_data",
        justification="No se encontró evidencia ecotoxicológica estandarizada suficiente sobre su tasa de degradación en efluentes urbanos.",
        source="CosIng (Sin datos ecotox)",
        source_url="https://ec.europa.eu/growth/tools-databases/cosing/",
        last_reviewed="2026-02-14"
    ),
    IngredienteDto(
        id="ing_0100",
        inci_name="Minthostachys Mollis Oil",
        synonyms=["aceite esencial de muña", "extracto de muna"],
        category="fragancia / activo botánico",
        water_impact_weight=None,
        status="insufficient_data",
        justification="No se encontró evidencia suficiente sobre su impacto crónico en organismos acuáticos en las bases ECHA o EPA.",
        source="Revisión Local",
        source_url="https://echa.europa.eu/",
        last_reviewed="2026-02-14"
    ),
]
