"""
Gera PDF de notificacao de novo lead com perguntas e respostas mapeadas.
Usa DejaVu (Unicode TTF) se disponivel, caso contrario Helvetica com sanitizacao.
"""
import base64
import os
from datetime import datetime
from fpdf import FPDF

# Fontes DejaVu sao instaladas por padrao no Ubuntu/Debian
_DEJAVU      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_USE_UNICODE = os.path.exists(_DEJAVU)


def _get_valor(payload: dict, campo: str):
    """Resolve valor do payload por chave direta ou notacao de ponto."""
    if not campo:
        return None
    if campo in payload:
        return payload[campo]
    atual = payload
    for parte in campo.split("."):
        if isinstance(atual, dict) and parte in atual:
            atual = atual[parte]
        else:
            return None
    return atual


def _limpar_label(campo: str) -> str:
    """Extrai a parte legivel do caminho do campo (ultima parte com espaco ou inicial maiuscula)."""
    partes = campo.split(".")
    for parte in reversed(partes):
        if " " in parte or (parte and parte[0].isupper()):
            return parte
    return partes[-1] if partes else campo


def _safe(texto) -> str:
    """Garante string sem caracteres fora do Latin-1 (fallback para Helvetica)."""
    s = str(texto) if texto is not None else ""
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _truncar(texto: str, limite: int = 220) -> str:
    t = str(texto) if texto is not None else ""
    return t[:limite] + "..." if len(t) > limite else t


def gerar_pdf_lead(
    nome: str,
    telefone: str,
    email: str,
    score: int,
    payload: dict,
    mapeamento: dict,
    empresa_nome: str = "",
) -> str:
    """
    Gera PDF com as perguntas e respostas mapeadas no webhook.
    Retorna base64.
    """
    pdf = FPDF()

    # Registra fontes Unicode se disponivel
    if _USE_UNICODE:
        pdf.add_font("DejaVu",     fname=_DEJAVU,      uni=True)
        pdf.add_font("DejaVuB",    fname=_DEJAVU_BOLD,  uni=True)
        F_NORMAL = "DejaVu"
        F_BOLD   = "DejaVuB"
    else:
        F_NORMAL = "Helvetica"
        F_BOLD   = "Helvetica"

    def txt(s):
        return s if _USE_UNICODE else _safe(s)

    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Cabecalho verde
    pdf.set_fill_color(29, 158, 117)
    pdf.rect(0, 0, 210, 32, style="F")
    pdf.set_y(10)
    pdf.set_font(F_BOLD, size=18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, txt("Leadflow - Novo Lead Recebido"), align="C")

    if empresa_nome:
        pdf.ln(8)
        pdf.set_font(F_NORMAL, size=11)
        pdf.cell(0, 6, txt(empresa_nome), align="C")

    pdf.ln(18)

    # Data/hora
    pdf.set_font(F_NORMAL, size=9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, txt(f"Recebido em: {datetime.now().strftime('%d/%m/%Y - %H:%M')}"), align="R")
    pdf.ln(10)

    # Caixa de resumo
    pdf.set_fill_color(240, 250, 246)
    pdf.set_draw_color(29, 158, 117)
    pdf.set_line_width(0.3)
    pdf.rect(20, pdf.get_y(), 170, 46, style="FD")
    pdf.set_xy(24, pdf.get_y() + 5)

    pdf.set_font(F_BOLD, size=12)
    pdf.set_text_color(29, 158, 117)
    pdf.cell(0, 7, txt("Dados Principais"), ln=True)

    def linha(label, valor):
        pdf.set_font(F_BOLD, size=10)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(24)
        pdf.cell(40, 7, txt(f"{label}:"), ln=False)
        pdf.set_font(F_NORMAL, size=10)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 7, txt(str(valor) if valor else "-"), ln=True)

    linha("Nome",     nome)
    linha("Telefone", telefone)
    linha("E-mail",   email)

    # Score com cor
    pdf.set_x(24)
    pdf.set_font(F_BOLD, size=10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(40, 7, txt("Score:"), ln=False)
    pdf.set_text_color(*(29, 158, 117) if score >= 10000 else (220, 100, 50))
    pdf.cell(0, 7, f"{score:,}".replace(",", "."), ln=True)

    pdf.ln(12)

    # Secao de perguntas e respostas
    pdf.set_fill_color(29, 158, 117)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(F_BOLD, size=11)
    pdf.cell(0, 9, txt("  Perguntas e Respostas"), fill=True, ln=True)
    pdf.ln(4)

    # Monta lista de pares (pergunta, resposta) a partir do mapeamento
    pares = []
    for variavel, campo_payload in mapeamento.items():
        if not campo_payload:
            continue
        valor = _get_valor(payload, campo_payload)
        if valor is None:
            continue
        pergunta = _limpar_label(campo_payload)
        pares.append((pergunta, _truncar(str(valor))))

    if pares:
        fill = False
        for pergunta, resposta in pares:
            pdf.set_fill_color(*(245, 252, 249) if fill else (255, 255, 255))

            # Pergunta (label em verde escuro, negrito)
            pdf.set_font(F_BOLD, size=9)
            pdf.set_text_color(20, 90, 60)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, txt(pergunta), fill=True)

            # Resposta (texto normal, ligeiramente indentado)
            pdf.set_font(F_NORMAL, size=10)
            pdf.set_text_color(30, 30, 30)
            pdf.set_x(24)
            pdf.multi_cell(166, 7, txt(resposta), fill=True)

            # Linha divisoria
            pdf.set_draw_color(210, 235, 225)
            pdf.set_line_width(0.2)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(3)
            fill = not fill
    else:
        pdf.set_font(F_NORMAL, size=10)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, txt("  Nenhuma resposta mapeada encontrada."), ln=True)

    # Rodape
    pdf.set_y(-18)
    pdf.set_font(F_NORMAL, size=8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 6, txt("Gerado automaticamente pelo Leadflow"), align="C")

    return base64.b64encode(bytes(pdf.output())).decode("utf-8")
