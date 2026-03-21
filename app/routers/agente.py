"""
Router do Agente IA — recebe mensagens do WhatsApp via Evolution API
e responde usando LLM configurado pela empresa.
Suporta function calling para agendamento no Google Agenda (Gemini).
"""
import json
import re
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.client import get_supabase
from app.services.evolution import enviar_mensagem
from app.services.llm import gerar_resposta
from app.services.google_calendar import criar_evento_calendar, buscar_horarios_livres, verificar_slot_livre

router = APIRouter(tags=["agente"])


async def _gerar_resposta_openai_com_agenda(
    modelo: str,
    api_key: str,
    system_prompt: str,
    mensagem: str,
    temperatura: float,
    max_tokens: int,
    calendar_creds: dict,
    calendar_id: str,
    fuso: str,
    lead: dict,
) -> str:
    """Chama OpenAI com function calling para agendamento no Google Agenda."""
    import asyncio
    import os
    from openai import AsyncOpenAI

    key = api_key or os.getenv("OPENAI_API_KEY", "")
    client = AsyncOpenAI(api_key=key)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "buscar_horarios_livres",
                "description": "Consulta o Google Agenda e retorna horários reais disponíveis. Use ANTES de sugerir horários ao lead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dias": {"type": "integer", "description": "Quantos dias à frente verificar (padrão 2)"}
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "criar_agendamento",
                "description": "Cria agendamento no Google Agenda quando lead confirmar data e hora.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "titulo":          {"type": "string",  "description": "Título do evento"},
                        "data":            {"type": "string",  "description": "Data no formato YYYY-MM-DD"},
                        "hora_inicio":     {"type": "string",  "description": "Hora de início no formato HH:MM"},
                        "duracao_minutos": {"type": "integer", "description": "Duração em minutos (padrão 60)"},
                        "descricao":       {"type": "string",  "description": "Descrição com dados do lead"},
                    },
                    "required": ["titulo", "data", "hora_inicio"],
                },
            },
        },
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": mensagem},
    ]

    for _ in range(6):
        resp = await client.chat.completions.create(
            model=modelo,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperatura,
            max_tokens=max_tokens,
        )

        msg = resp.choices[0].message
        tool_calls = msg.tool_calls

        if not tool_calls:
            return msg.content or ""

        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in tool_calls
        ]})

        for tc in tool_calls:
            import json as _json
            args = _json.loads(tc.function.arguments or "{}")
            try:
                if tc.function.name == "buscar_horarios_livres":
                    _cvf = calendars_verificar
                    slots = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: buscar_horarios_livres(
                            credentials_dict=calendar_creds,
                            calendar_id=calendar_id,
                            calendars_verificar=_cvf,
                            fuso=fuso,
                            dias=int(args.get("dias", 3)),
                        )
                    )
                    fn_result = f"Horários livres: {', '.join(slots)}" if slots else "Nenhum horário livre nos próximos dias."
                elif tc.function.name == "criar_agendamento":
                    data_ev      = args["data"]
                    hora_ev      = args["hora_inicio"]
                    duracao_ev   = int(args.get("duracao_minutos", 60))
                    _cvf2 = calendars_verificar
                    slot_livre = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: verificar_slot_livre(
                            credentials_dict=calendar_creds,
                            calendar_id=calendar_id,
                            calendars_verificar=_cvf2,
                            data=data_ev,
                            hora_inicio=hora_ev,
                            duracao_minutos=duracao_ev,
                            fuso=fuso,
                        )
                    )
                    if not slot_livre:
                        _cvf3 = calendars_verificar
                        slots = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: buscar_horarios_livres(
                                credentials_dict=calendar_creds,
                                calendar_id=calendar_id,
                                calendars_verificar=_cvf3,
                                fuso=fuso,
                                dias=3,
                            )
                        )
                        alternativas = ", ".join(slots) if slots else "nenhum horário livre nos próximos dias"
                        fn_result = f"Horário {hora_ev} do dia {data_ev} já está ocupado na agenda. Horários disponíveis: {alternativas}"
                    else:
                        resultado = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: criar_evento_calendar(
                                credentials_dict=calendar_creds,
                                calendar_id=calendar_id,
                                titulo=args.get("titulo", f"Sessão Estratégica — {lead.get('nome', '')}"),
                                data=data_ev,
                                hora_inicio=hora_ev,
                                duracao_minutos=duracao_ev,
                                descricao=args.get("descricao", ""),
                                fuso=fuso,
                            )
                        )
                        fn_result = f"Agendamento criado! Link: {resultado['link']}"
                else:
                    fn_result = "Função não reconhecida."
            except Exception as e:
                fn_result = f"Erro: {str(e)}"

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": fn_result})

    return ""


async def _gerar_resposta_gemini_com_agenda(
    modelo: str,
    api_key: str,
    system_prompt: str,
    mensagem: str,
    temperatura: float,
    max_tokens: int,
    calendar_creds: dict,
    calendar_id: str,
    fuso: str,
    lead: dict,
) -> str:
    """Chama Gemini com function calling para agendamento no Google Agenda."""
    from google import genai
    from google.genai import types
    import asyncio
    import os

    key = api_key or os.getenv("GEMINI_API_KEY", "")
    client = genai.Client(api_key=key)

    tool_agenda = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="buscar_horarios_livres",
            description=(
                "Consulta o Google Agenda e retorna os horários reais disponíveis para os próximos dias. "
                "Use ANTES de sugerir horários ao lead para mostrar opções reais."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "dias": types.Schema(type=types.Type.INTEGER, description="Quantos dias à frente verificar (padrão 2)"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="criar_agendamento",
            description=(
                "Cria um agendamento no Google Agenda quando o lead confirmar data e hora. "
                "Use apenas quando tiver data E hora confirmadas pelo lead."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "titulo":          types.Schema(type=types.Type.STRING,  description="Título do evento"),
                    "data":            types.Schema(type=types.Type.STRING,  description="Data no formato YYYY-MM-DD"),
                    "hora_inicio":     types.Schema(type=types.Type.STRING,  description="Hora de início no formato HH:MM"),
                    "duracao_minutos": types.Schema(type=types.Type.INTEGER, description="Duração em minutos (padrão 60)"),
                    "descricao":       types.Schema(type=types.Type.STRING,  description="Descrição com dados do lead"),
                },
                required=["titulo", "data", "hora_inicio"],
            ),
        ),
    ])

    cfg = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperatura,
        max_output_tokens=max_tokens,
        tools=[tool_agenda],
    )

    contents = [types.Content(role="user", parts=[types.Part(text=mensagem)])]

    for _ in range(6):  # máximo 6 rounds (3 tool calls + respostas)
        resp = await client.aio.models.generate_content(
            model=modelo, contents=contents, config=cfg,
        )

        candidate = resp.candidates[0] if resp.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            break

        fn_parts = [p for p in candidate.content.parts if p.function_call]

        if not fn_parts:
            # Sem function calls — extrai texto e retorna
            for p in candidate.content.parts:
                if hasattr(p, "text") and p.text:
                    return p.text
            break

        # Adiciona resposta do modelo com as function calls ao contexto
        contents.append(types.Content(role="model", parts=candidate.content.parts))

        # Executa cada função e coleta resultados
        fn_responses = []
        for part in fn_parts:
            fc = part.function_call
            args = dict(fc.args) if fc.args else {}
            try:
                if fc.name == "buscar_horarios_livres":
                    slots = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: buscar_horarios_livres(
                            credentials_dict=calendar_creds,
                            calendar_id=calendar_id,
                            fuso=fuso,
                            dias=int(args.get("dias", 2)),
                        )
                    )
                    fn_result = f"Horários livres: {', '.join(slots)}" if slots else "Nenhum horário livre nos próximos dias."

                elif fc.name == "criar_agendamento":
                    resultado = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: criar_evento_calendar(
                            credentials_dict=calendar_creds,
                            calendar_id=calendar_id,
                            titulo=args.get("titulo", f"Sessão Estratégica — {lead.get('nome', '')}"),
                            data=args["data"],
                            hora_inicio=args["hora_inicio"],
                            duracao_minutos=int(args.get("duracao_minutos", 60)),
                            descricao=args.get("descricao", ""),
                            fuso=fuso,
                        )
                    )
                    fn_result = f"Agendamento criado com sucesso! Link: {resultado['link']}"
                else:
                    fn_result = "Função não reconhecida."
            except Exception as e:
                fn_result = f"Erro ao executar função: {str(e)}"

            fn_responses.append(types.Part(
                function_response=types.FunctionResponse(
                    name=fc.name, response={"result": fn_result}
                )
            ))

        contents.append(types.Content(role="user", parts=fn_responses))

    return ""


def _limpar_numero(numero: str) -> str:
    return re.sub(r"\D", "", numero)


def _substituir_variaveis(template: str, lead: dict, empresa_nome: str) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    replacements = {
        "{{lead.nome}}":     lead.get("nome", ""),
        "{{lead.telefone}}": lead.get("telefone", ""),
        "{{lead.email}}":    lead.get("email", ""),
        "{{lead.empresa}}":  lead.get("dados_raw", {}).get("empresa", "") if isinstance(lead.get("dados_raw"), dict) else "",
        "{{lead.interesse}}": lead.get("dados_raw", {}).get("interesse", "") if isinstance(lead.get("dados_raw"), dict) else "",
        "{{empresa_nome}}":  empresa_nome,
        "{{data_hora}}":     now,
    }
    for k, v in replacements.items():
        template = template.replace(k, str(v))
    return template


@router.post("/agente/evolution/webhook")
async def receber_mensagem_evolution(request: Request):
    """
    Recebe eventos do webhook da Evolution API (mensagens recebidas de leads).
    Configure na Evolution API: Webhook URL → https://<backend>/agente/evolution/webhook
    Eventos: MESSAGES_UPSERT
    """
    try:
        body = await request.body()
        try:
            payload = json.loads(body.decode("utf-8"))
        except UnicodeDecodeError:
            payload = json.loads(body.decode("latin-1"))
    except Exception as e:
        return JSONResponse({"ok": False, "erro": f"Payload inválido: {str(e)}"}, status_code=400)

    # Evolution API envia evento com campo "event"
    event = payload.get("event", "")
    if event not in ("messages.upsert", "MESSAGES_UPSERT", "message.upsert"):
        return {"ok": True, "ignorado": True, "event": event}

    data = payload.get("data", {})
    # Ignora mensagens enviadas pelo próprio bot (fromMe)
    key = data.get("key", {})
    if key.get("fromMe", False):
        return {"ok": True, "ignorado": True, "motivo": "fromMe"}

    # Extrai número e texto da mensagem
    numero_remoto = key.get("remoteJid", "")
    numero = _limpar_numero(numero_remoto.split("@")[0])
    if not numero:
        return {"ok": True, "ignorado": True, "motivo": "sem numero"}

    mensagem_entrada = (
        data.get("message", {}).get("conversation")
        or data.get("message", {}).get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    if not mensagem_entrada:
        return {"ok": True, "ignorado": True, "motivo": "sem texto"}

    # Nome da instância (para identificar a empresa)
    instancia = payload.get("instance", "")

    try:
        sb = get_supabase()

        # Encontra empresa pela instância Evolution
        empresa_res = sb.table("empresas") \
            .select("id, nome, evolution_instancia, config_apis, config_ia") \
            .execute()
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "erro": f"Erro ao consultar empresas: {str(e)}", "trace": traceback.format_exc()}, status_code=500)

    empresa = None
    for e in (empresa_res.data or []):
        inst = e.get("evolution_instancia") or (e.get("config_apis") or {}).get("evolution_instancia", "")
        if inst and inst.lower() == instancia.lower():
            empresa = e
            break

    if not empresa:
        return {"ok": False, "erro": f"Empresa não encontrada para instância '{instancia}'"}

    empresa_id  = empresa["id"]
    empresa_nome = empresa.get("nome", "")
    config_apis = empresa.get("config_apis") or {}
    config_ia   = empresa.get("config_ia") or {}

    # Busca lead pelo telefone
    lead_res = sb.table("leads") \
        .select("*") \
        .eq("empresa_id", empresa_id) \
        .eq("telefone", numero) \
        .order("criado_em", desc=True) \
        .limit(1).execute()

    lead = lead_res.data[0] if lead_res.data else {"nome": numero, "telefone": numero, "dados_raw": {}}

    # Verifica se agente está pausado
    if config_ia.get("agente_pausado", False):
        return {"ok": True, "ignorado": True, "motivo": "agente pausado"}

    # Verifica score mínimo
    score_minimo = int(config_ia.get("score_minimo", 10000))
    score = int(lead.get("score", 0) or 0)
    if score < score_minimo:
        return {"ok": True, "ignorado": True, "motivo": "score abaixo do mínimo", "score": score}

    # Busca histórico de conversa (últimas 10 mensagens)
    hist_res = sb.table("conversas") \
        .select("role, conteudo") \
        .eq("empresa_id", empresa_id) \
        .eq("telefone", numero) \
        .order("criado_em", desc=False) \
        .limit(10).execute()

    historico = [{"role": h["role"], "content": h["conteudo"]} for h in (hist_res.data or [])]

    # Monta system prompt com variáveis substituídas
    prompt_sistema = _substituir_variaveis(
        config_ia.get("prompt_sistema", "Você é um assistente de vendas."),
        lead,
        empresa_nome,
    )

    # Monta mensagem para o LLM (histórico + mensagem atual)
    mensagem_llm = ""
    for h in historico:
        role_label = "Agente" if h["role"] == "assistant" else "Lead"
        mensagem_llm += f"{role_label}: {h['content']}\n"
    mensagem_llm += f"Lead: {mensagem_entrada}"

    # Seleciona chave de API correta para o provider
    modelo   = config_ia.get("modelo", "gemini-2.0-flash")
    provider = config_ia.get("provider", "")
    provider_map = {
        "gemini":    config_apis.get("gemini_key", ""),
        "anthropic": config_apis.get("anthropic_key", ""),
        "openai":    config_apis.get("openai_key", ""),
    }
    prov = provider or ("gemini" if modelo.startswith("gemini") else "anthropic" if modelo.startswith("claude") else "openai")
    api_key = provider_map.get(prov, "")

    # Configurações do Google Agenda
    calendar_creds      = config_apis.get("google_calendar_credentials")
    calendar_id         = config_apis.get("google_calendar_id", "primary")
    calendars_verificar = config_apis.get("google_calendars_verificar") or []
    fuso                = empresa.get("fuso") or "America/Sao_Paulo"

    # Gera resposta — Gemini com function calling se agenda configurada
    resposta = ""
    try:
        if prov == "openai" and calendar_creds:
            resposta = await _gerar_resposta_openai_com_agenda(
                modelo=modelo,
                api_key=api_key,
                system_prompt=prompt_sistema,
                mensagem=mensagem_llm,
                temperatura=float(config_ia.get("temperatura", 0.7)),
                max_tokens=int(config_ia.get("max_tokens", 800)),
                calendar_creds=calendar_creds,
                calendar_id=calendar_id,
                fuso=fuso,
                lead=lead,
            )
        elif prov == "gemini" and calendar_creds:
            resposta = await _gerar_resposta_gemini_com_agenda(
                modelo=modelo,
                api_key=api_key,
                system_prompt=prompt_sistema,
                mensagem=mensagem_llm,
                temperatura=float(config_ia.get("temperatura", 0.7)),
                max_tokens=int(config_ia.get("max_tokens", 500)),
                calendar_creds=calendar_creds,
                calendar_id=calendar_id,
                fuso=fuso,
                lead=lead,
            )
        else:
            resposta = await gerar_resposta(
                modelo=modelo,
                system_prompt=prompt_sistema,
                mensagem=mensagem_llm,
                api_key=api_key,
                temperatura=float(config_ia.get("temperatura", 0.7)),
                max_tokens=int(config_ia.get("max_tokens", 500)),
                provider=prov,
            )
    except Exception as e:
        return JSONResponse({"ok": False, "erro": f"Erro ao gerar resposta: {str(e)}"}, status_code=500)

    if not resposta:
        return {"ok": True, "ignorado": True, "motivo": "resposta vazia do LLM"}

    # Salva mensagens no histórico
    agora = datetime.utcnow().isoformat()
    try:
        sb.table("conversas").insert([
            {"empresa_id": empresa_id, "telefone": numero, "role": "user",      "conteudo": mensagem_entrada, "criado_em": agora},
            {"empresa_id": empresa_id, "telefone": numero, "role": "assistant",  "conteudo": resposta,         "criado_em": agora},
        ]).execute()
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "erro": f"Erro ao salvar histórico: {str(e)}", "trace": traceback.format_exc()}, status_code=500)

    # Envia resposta via Evolution API
    import os
    evo_url       = config_apis.get("evolution_url", "") or os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    evo_key       = config_apis.get("evolution_key", "") or os.getenv("EVOLUTION_API_KEY", "")
    evo_instancia = (empresa.get("evolution_instancia") or config_apis.get("evolution_instancia", "")) or os.getenv("EVOLUTION_INSTANCIA", "")

    envio = {}
    try:
        if evo_url and evo_key and evo_instancia:
            envio = await enviar_mensagem(evo_url, evo_key, evo_instancia, numero, resposta)
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "erro": f"Erro ao enviar WhatsApp: {str(e)}", "trace": traceback.format_exc()}, status_code=500)

    return {"ok": True, "resposta": resposta, "envio": envio}


@router.post("/agente/testar")
async def testar_agente(body: dict):
    """
    Testa o agente IA sem enviar WhatsApp.
    Body: { empresa_id, lead: { nome, interesse, empresa } }
    """
    empresa_id = body.get("empresa_id", "")
    lead_teste  = body.get("lead", {})

    sb = get_supabase()
    empresa_res = sb.table("empresas") \
        .select("nome, config_apis, config_ia") \
        .eq("id", empresa_id).limit(1).execute()

    if not empresa_res.data:
        return JSONResponse({"ok": False, "erro": "Empresa não encontrada"}, status_code=404)

    empresa     = empresa_res.data[0]
    empresa_nome = empresa.get("nome", "")
    config_apis = empresa.get("config_apis") or {}
    config_ia   = empresa.get("config_ia") or {}

    # Lead sintético com dados_raw para variáveis
    lead = {
        "nome":      lead_teste.get("nome", "Lead Teste"),
        "telefone":  lead_teste.get("telefone", ""),
        "email":     lead_teste.get("email", ""),
        "dados_raw": {"interesse": lead_teste.get("interesse", ""), "empresa": lead_teste.get("empresa", "")},
    }

    prompt_sistema = _substituir_variaveis(
        config_ia.get("prompt_sistema", "Você é um assistente de vendas da {{empresa_nome}}."),
        lead,
        empresa_nome,
    )

    mensagem_usuario = (
        f"Olá! Me chamo {lead['nome']} e tenho interesse em {lead_teste.get('interesse', 'seus produtos')}."
    )

    modelo   = config_ia.get("modelo", "gemini-2.0-flash")
    provider = config_ia.get("provider", "")
    prov = provider or ("gemini" if modelo.startswith("gemini") else "anthropic" if modelo.startswith("claude") else "openai")
    provider_map = {
        "gemini":    config_apis.get("gemini_key", ""),
        "anthropic": config_apis.get("anthropic_key", ""),
        "openai":    config_apis.get("openai_key", ""),
    }
    api_key = provider_map.get(prov, "")

    try:
        resposta = await gerar_resposta(
            modelo=modelo,
            system_prompt=prompt_sistema,
            mensagem=mensagem_usuario,
            api_key=api_key,
            temperatura=float(config_ia.get("temperatura", 0.7)),
            max_tokens=int(config_ia.get("max_tokens", 500)),
            provider=prov,
        )
        return {"ok": True, "mensagem": resposta}
    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=500)
