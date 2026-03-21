"""
Gera PDF de notificacao de novo lead com as perguntas e respostas mapeadas.
Usa apenas caracteres Latin-1 para compatibilidade com fonte Helvetica.
"""
import base64
from datetime import datetime
from fpdf import FPDF


def _get_valor(payload: dict, campo: str):
    """Resolve valor do payload por chave direta ou notacao de ponto."""
    if not campo:
        return None
    if campo in payload:
        return payload[campo]
    partes = campo.split(".")
    atual = payload
    for parte in partes:
        if isinstance(atual, dict) and parte in atual:
            atual = atual[parte]
        else:
            return None
    return atual


def _limpar_label(campo: str) -> str:
    """Extrai a parte legivel do caminho do campo."""
    partes = campo.split(".")
    for parte in reversed(partes):
        if " " in parte or (parte and parte[0].isupper()):
            return parte
    return partes[-1] if partes else campo


def _safe(texto) -> str:
    """Converte para string Latin-1 segura para Helvetica."""
    s = str(texto) if texto is not None else "-"
    s = (s
         .replace("\u2014", "-").replace("\u2013", "-")
         .replace("\u2026", "...").replace("\u2019", "'")
         .replace("\u201c", '"').replace("\u201d", '"')
         .replace("\u00e0", "a").replace("\u00e1", "a")
         .replace("\u00e2", "a").replace("\u00e3", "a")
         .replace("\u00e9", "e").replace("\u00ea", "e")
         .replace("\u00ed", "i").replace("\u00f3", "o")
         .replace("\u00f4", "o").replace("\u00f5", "o")
         .replace("\u00fa", "u").replace("\u00fc", "u")
         .replace("\u00c0", "A").replace("\u00c1", "A")
         .replace("\u00c2", "A").replace("\u00c3", "A")
         .replace("\u00c9", "E").replace("\u00ca", "E")
         .replace("\u00cd", "I").replace("\u00d3", "O")
         .replace("\u00d4", "O").replace("\u00d5", "O")
         .replace("\u00da", "U").replace("\u00c7", "C")
         .replace("\u00e7", "c"))
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _truncar(texto: str, limite: int = 200) -> str:
    t = _safe(texto)
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
    mapeamento: { variavel -> campo_do_payload }
    """

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Cabecalho
    pdf.set_fill_color(29, 158, 117)
    pdf.rect(0, 0, 210, 32, style="F")

    pdf.set_y(10)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "Leadflow - Novo Lead Recebido", align="C")

    if empresa_nome:
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, _safe(empresa_nome), align="C")

    pdf.ln(18)
    pdf.set_text_color(30, 30, 30)

    # Data/hora
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Recebido em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", align="R")
    pdf.ln(10)

    # Resumo principal
    pdf.set_fill_color(240, 250, 246)
    pdf.set_draw_color(29, 158, 117)
    pdf.set_line_width(0.3)
    pdf.rect(20, pdf.get_y(), 170, 42, style="FD")
    pdf.set_xy(24, pdf.get_y() + 5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(29, 158, 117)
    pdf.cell(0, 7, "Dados Principais", ln=True)

    def linha_resumo(label, valor):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(24)
        pdf.cell(40, 7, f"{label}:", ln=False)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 7, _safe(valor) if valor else "-", ln=True)

    linha_resumo("Nome",     nome)
    linha_resumo("Telefone", telefone)
    linha_resumo("E-mail",   email)

    pdf.set_x(24)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(40, 7, "Score:", ln=False)
    score_color = (29, 158, 117) if score >= 10000 else (220, 100, 50)
    pdf.set_text_color(*score_color)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"{score:,}".replace(",", "."), ln=True)

    pdf.ln(12)

    # Perguntas e Respostas Mapeadas
    pdf.set_fill_color(29, 158, 117)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "  Perguntas e Respostas", fill=True, ln=True)
    pdf.ln(4)

    pares = []
    for variavel, campo_payload in mapeamento.items():
        if not campo_payload:
            continue
        valor = _get_valor(payload, campo_payload)
        if valor is None:
            continue
        pergunta = _limpar_label(campo_payload)
        pares.append((_safe(pergunta), _truncar(str(valor))))

    if pares:
        fill = False
        for pergunta, resposta in pares:
            fill_color = (245, 252, 249) if fill else (255, 255, 255)
            pdf.set_fill_color(*fill_color)

            # Pergunta
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(29, 100, 75)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, pergunta, fill=True)

            # Resposta
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
            pdf.set_x(24)
            pdf.multi_cell(166, 7, resposta, fill=True)

            pdf.set_draw_color(220, 240, 232)
            pdf.set_line_width(0.2)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(3)
            fill = not fill
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, "  Nenhuma resposta mapeada encontrada.", ln=True)

    # Rodape
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 6, "Gerado automaticamente pelo Leadflow", align="C")

    pdf_bytes = bytes(pdf.output())
    return base64.b64encode(pdf_bytes).decode("utf-8")
