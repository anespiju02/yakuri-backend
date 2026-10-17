from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.sqlite_repo import init_db
from app.routers import ingredientes, escaneos, auditorias_eticas, metricas


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Yakuri API — Especificación OpenAPI 3.1",
    description="Contrato OpenAPI para generación automática de cliente Angular (Secciones 4, 5, 6 y 9).",
    version="1.0.0",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:8000", "description": "Servidor de Desarrollo Local"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingredientes.router)
app.include_router(escaneos.router)
app.include_router(auditorias_eticas.router)
app.include_router(metricas.router)


@app.get("/api/v1/salud", tags=["Sistema"], operation_id="verificarEstadoApi")
def verificar_estado_api():
    return {"status": "ok", "service": "yakuri-backend", "openapi_version": app.openapi_version}
