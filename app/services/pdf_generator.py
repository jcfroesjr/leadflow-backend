"""
Gera PDF de notificação de novo lead com todos os campos do webhook.
"""
import base64
from datetime import datetime
from fpdf import FPDF


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
    Gera um PDF com os dados do lead e retorna como string base64.
    """

    # Mapeamento invertido: campo_payload → nome_amigavel
    mapa_invertido = {v: k for k, v in mapeamento.items() if isinstance(v, str)}

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    pdf.set_fill_color(29, 158, 117)  # brand green
    pdf.rect(0, 0, 210, 32, style="F")

    pdf.set_y(10)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "Leadflow  —  Novo Lead Recebido", align="C")

    if empresa_nome:
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, empresa_nome, align="C")

    pdf.ln(18)
    pdf.set_text_color(30, 30, 30)

    # ── Data/hora ─────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Recebido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", align="R")
    pdf.ln(10)

    # ── Resumo principal ─────────────────────────────────────────────────
    pdf.set_fill_color(240, 250, 246)
    pdf.set_draw_color(29, 158, 117)
    pdf.set_line_width(0.3)
    pdf.rect(20, pdf.get_y(), 170, 42, style="FD")
    pdf.set_xy(24, pdf.get_y() + 5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(29, 158, 117)
    pdf.cell(0, 7, "Dados Principais", ln=True)
    pdf.set_x(24)

    def linha_resumo(label, valor):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(24)
        pdf.cell(40, 7, f"{label}:", ln=False)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 7, str(valor) if valor else "—", ln=True)

    linha_resumo("Nome",     nome or "—")
    linha_resumo("Telefone", telefone or "—")
    linha_resumo("E-mail",   email or "—")

    # Score com cor
    pdf.set_x(24)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(40, 7, "Score:", ln=False)
    score_color = (29, 158, 117) if score >= 10000 else (220, 100, 50)
    pdf.set_text_color(*score_color)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"{score:,}".replace(",", "."), ln=True)

    pdf.ln(12)

    # ── Todos os campos do payload ────────────────────────────────────────
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(29, 158, 117)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  Respostas Completas do Webhook", fill=True, ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(248, 248, 248)
    pdf.set_fill_color(240, 250, 246)

    fill = False
    for campo, valor in payload.items():
        if isinstance(valor, dict):
            # Sub-objeto: mostrar como bloco
            nome_campo = mapa_invertido.get(campo, campo).replace("_", " ").title()
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(230, 244, 238)
            pdf.cell(0, 7, f"  {nome_campo}", fill=True, ln=True)
            for sub_campo, sub_valor in valor.items():
                nome_sub = sub_campo.replace("_", " ").title()
                pdf.set_font("Helvetica", "", 9)
                pdf.set_fill_color(250, 250, 250)
                pdf.set_x(24)
                pdf.cell(55, 6, f"  {nome_sub}:", fill=True)
                pdf.cell(0, 6, _truncar(str(sub_valor)), fill=True, ln=True)
            continue

        nome_campo = mapa_invertido.get(campo, campo).replace("_", " ").title()
        fill_color = (245, 245, 245) if fill else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(55, 7, f"  {nome_campo}", fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 7, _truncar(str(valor) if valor is not None else "—"), fill=True, ln=True)
        fill = not fill

    # ── Rodapé ───────────────────────────────────────────────────────────
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 6, "Gerado automaticamente pelo Leadflow", align="C")

    pdf_bytes = bytes(pdf.output())
    return base64.b64encode(pdf_bytes).decode("utf-8")


def _truncar(texto: str, limite: int = 90) -> str:
    return texto[:limite] + "…" if len(texto) > limite else texto
