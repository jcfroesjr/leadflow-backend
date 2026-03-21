import json
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.client import get_supabase
from app.services.evolution import enviar_mensagem, enviar_documento
from app.services.pdf_generator import gerar_pdf_lead

router = APIRouter(tags=["webhook"])

# Fallback para variáveis de ambiente (caso não configurado por empresa)
EVOLUTION_URL_ENV = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY_ENV = os.getenv("EVOLUTION_API_KEY", "")


@router.post("/webhook/{empresa_id}/{token}")
async def receber_webhook(empresa_id: str, token: str, request: Request):
    # Lê body com suporte a UTF-8 e Latin-1
    try:
        body = await request.body()
        try:
            payload = json.loads(body.decode("utf-8"))
        except UnicodeDecodeError:
            payload = json.loads(body.decode("latin-1"))
    except Exception as e:
        return JSONResponse({"ok": False, "erro": f"Payload inválido: {str(e)}"}, status_code=400)

    try:
        sb = get_supabase()

        # Valida webhook
        result = sb.table("webhooks").select("*") \
            .eq("empresa_id", empresa_id) \
            .eq("token", token) \
            .eq("ativo", True) \
            .limit(1).execute()

        if not result.data:
            return {"ok": False, "erro": "Webhook não encontrado"}

        wh = result.data[0]

        # Resolve valores aninhados via notação de ponto (ex: respondent.answers.Nome)
        def _get_nested(obj, path):
            if not path:
                return None
            if path in obj:
                return obj[path]
            atual = obj
            for parte in path.split("."):
                if isinstance(atual, dict) and parte in atual:
                    atual = atual[parte]
                else:
                    return None
            return atual

        def _extrair(campo_chave, fallback):
            mapa_lower = {k.lower(): v for k, v in mapa.items()}
            caminho = mapa_lower.get(campo_chave.lower())
            if caminho:
                val = _get_nested(payload, caminho)
                if val is not None:
                    return str(val)
            return payload.get(fallback, "")

        # Mapeia campos usando mapeamento configurado
        mapa     = wh.get("mapeamento_campos") or {}
        nome     = _extrair("nome",     "nome")
        telefone = _extrair("telefone", "telefone")
        email    = _extrair("email",    "email")

        # Score — busca case-insensitive e resolve caminho aninhado
        mapa_lower  = {k.lower(): v for k, v in mapa.items()}
        campo_score = mapa_lower.get("score", "score")
        score_raw   = _get_nested(payload, campo_score) or payload.get("score", 0)
        try:
            score = int(float(str(score_raw)))
        except (ValueError, TypeError):
            score = 0

        # Salva lead com score
        sb.table("leads").insert({
            "empresa_id": empresa_id,
            "nome":       nome,
            "telefone":   telefone,
            "email":      email,
            "score":      score,
            "origem":     wh.get("plataforma", "webhook"),
            "status":     "pendente",
            "dados_raw":  payload,
        }).execute()

        # Busca configurações de Evolution e IA da empresa
        empresa_res = sb.table("empresas") \
            .select("nome, evolution_instancia, config_apis, config_ia") \
            .eq("id", empresa_id).limit(1).execute()

        agente_ativo = False

        if empresa_res.data:
            empresa      = empresa_res.data[0]
            empresa_nome = empresa.get("nome", "")
            config_apis  = empresa.get("config_apis") or {}
            config_ia    = empresa.get("config_ia") or {}

            evo_url       = config_apis.get("evolution_url") or EVOLUTION_URL_ENV
            evo_key       = config_apis.get("evolution_key") or EVOLUTION_KEY_ENV
            evo_instancia = empresa.get("evolution_instancia") or config_apis.get("evolution_instancia", "")

            # ── Notificações internas para equipe ────────────────────────────
            telefones_notif = config_apis.get("notificacoes_telefones") or []
            if telefones_notif and evo_url and evo_key and evo_instancia:
                score_fmt = f"{score:,}".replace(",", ".")
                numero_limpo = "".join(filter(str.isdigit, telefone or ""))
                wa_link = f"https://wa.me/{numero_limpo}" if numero_limpo else ""
                linhas = [
                    "🔔 *Novo lead recebido!*\n",
                    f"👤 *Nome:* {nome or '-'}",
                    f"📱 *Celular:* {telefone or '-'}",
                ]
                if email:
                    linhas.append(f"📧 *E-mail:* {email}")
                linhas += [
                    f"⭐ *Score:* {score_fmt}",
                    f"📋 *Origem:* {wh.get('nome') or wh.get('plataforma', 'webhook')}",
                ]
                texto_notif = "\n".join(linhas)

                # Gera PDF com os dados mapeados
                try:
                    pdf_b64 = gerar_pdf_lead(
                        nome=nome,
                        telefone=telefone,
                        email=email,
                        score=score,
                        payload=payload,
                        mapeamento=mapa,
                        empresa_nome=empresa_nome,
                    )
                except Exception:
                    pdf_b64 = None

                nome_arquivo = f"lead_{(nome or 'desconhecido').replace(' ', '_')}.pdf"

                for tel in telefones_notif:
                    tel = str(tel).strip()
                    if not tel:
                        continue
                    # 1. Mensagem de texto com resumo
                    await enviar_mensagem(evo_url, evo_key, evo_instancia, tel, texto_notif)
                    # 2. PDF com respostas (se gerado com sucesso)
                    if pdf_b64:
                        await enviar_documento(
                            evo_url, evo_key, evo_instancia, tel,
                            pdf_b64, nome_arquivo,
                            caption="",
                        )

            # ── Mensagem para o lead ──────────────────────────────────────────
            if telefone:
                score_minimo = int(config_ia.get("score_minimo", 10000))
                agente_ativo = score >= score_minimo

                if evo_url and evo_key and evo_instancia:
                    nome_display = nome or "cliente"

                    if agente_ativo:
                        mensagem = config_ia.get("mensagem_inicial") or \
                            f"Olá {nome_display}! 👋 Recebemos seu contato e nossa equipe entrará em contato em breve."
                    else:
                        mensagem = config_ia.get("mensagem_score_baixo") or \
                            f"Olá {nome_display}! Recebemos seu contato. Em breve retornaremos."

                    await enviar_mensagem(evo_url, evo_key, evo_instancia, telefone, mensagem)

        return {"ok": True, "score": score, "agente_acionado": agente_ativo}

    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=500)


@router.post("/teste/whatsapp")
async def testar_whatsapp(body: dict):
    """
    Endpoint para testar envio de mensagem WhatsApp diretamente.
    Body: { "numero": "5521...", "mensagem": "...", "instancia": "...", "evo_url": "...", "evo_key": "..." }
    """
    numero    = body.get("numero", "")
    mensagem  = body.get("mensagem", "Teste de mensagem do Leadflow!")
    instancia = body.get("instancia") or os.getenv("EVOLUTION_INSTANCIA", "")
    evo_url   = body.get("evo_url") or EVOLUTION_URL_ENV
    evo_key   = body.get("evo_key") or EVOLUTION_KEY_ENV

    if not all([numero, instancia, evo_url, evo_key]):
        return JSONResponse({"ok": False, "erro": "Campos obrigatórios: numero, instancia, evo_url, evo_key"}, status_code=400)

    resultado = await enviar_mensagem(evo_url, evo_key, instancia, numero, mensagem)
    return resultado
