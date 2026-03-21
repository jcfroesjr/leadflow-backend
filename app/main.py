from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import webhook, leads, configuracoes, agente, agenda

app = FastAPI(title="LeadFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(configuracoes.router)
app.include_router(agente.router)
app.include_router(agenda.router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "LeadFlow API funcionando!"}
