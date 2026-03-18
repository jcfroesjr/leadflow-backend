from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="LeadFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
from app.routers import webhook, leads, documentos, agente, configuracoes, usuarios, followup, agendamentos

app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(documentos.router)
app.include_router(agente.router)
app.include_router(configuracoes.router)
app.include_router(usuarios.router)
app.include_router(followup.router)
app.include_router(agendamentos.router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "env": os.getenv("ENVIRONMENT", "dev")}


@app.get("/")
async def root():
    return {"message": "LeadFlow API — acesse /docs para a documentação"}
