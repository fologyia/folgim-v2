import streamlit as st

from config import FREQ_MINIMA_PCT
from utils import nota_formatada  # noqa: F401 — re-exported for convenience


def divider():
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


def section_title(texto: str):
    st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)


def kpi_html(label: str, value: str, desc: str, variante: str = "") -> str:
    return f"""
    <div class="kpi-card {variante}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-desc">{desc}</div>
    </div>"""


def render_freq_card(freq: dict):
    """Renderiza o card de frequência no modo Aluno Individual."""
    if not freq["tem_dados"]:
        st.markdown("""
        <div style="background:#F8FAFC;border-radius:14px;padding:18px 22px;
                    border:1px dashed #D1D5DB;color:#9CA3AF;font-size:0.88rem;text-align:center">
            ⬜ Sem dados de frequência — adicione a aba <b>Frequência</b> na planilha
        </div>""", unsafe_allow_html=True)
        return

    pct       = freq["pct_presenca"]
    cor       = freq["cor"]
    restantes = freq["faltas_restantes"]

    barra_width = min(100, pct)

    if freq["status"] == "critico":
        msg_html = (
            f'<div class="freq-alerta">🚨 Frequência abaixo do mínimo ({FREQ_MINIMA_PCT:.0f}%). '
            f'Risco de reprovação por falta!</div>'
        )
    elif freq["status"] == "atencao":
        msg_html = (
            f'<div class="freq-alerta" style="background:#FFF7ED;border-color:#FED7AA;color:#9A3412">'
            f'⚠️ Frequência próxima do limite. Restam apenas <b>{restantes}</b> falta(s) antes de reprovar.'
            f'</div>'
        )
    else:
        msg_html = (
            f'<div class="freq-ok">✅ Frequência regular. '
            f'Pode faltar mais <b>{restantes}</b> dia(s) sem risco.</div>'
        )

    padrao_html = ""
    if freq["padrao_seg_sex"]:
        padrao_html = (
            f'<div style="background:#FEF3C7;border:1px solid #FDE68A;border-radius:8px;'
            f'padding:8px 12px;margin-top:10px;font-size:0.82rem;color:#92400E">'
            f'📅 <b>Padrão detectado:</b> {freq["pct_seg_sex"]:.0f}% das faltas caem em '
            f'segunda ou sexta-feira.</div>'
        )

    card = (
        f'<div class="freq-card" style="border-left-color:{cor}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">'
        f'<div style="font-weight:700;font-size:0.88rem;text-transform:uppercase;letter-spacing:0.07em;color:#374151">📅 Frequência</div>'
        f'<div style="font-family:Montserrat;font-weight:800;font-size:1.8rem;color:{cor}">{pct:.1f}%</div>'
        f'</div>'
        f'<div class="freq-barra-bg"><div class="freq-barra-fill" style="width:{barra_width}%;background:{cor}"></div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#9CA3AF;margin-top:4px">'
        f'<span>0%</span><span style="color:#E30613;font-weight:600">{FREQ_MINIMA_PCT:.0f}% mín.</span><span>100%</span>'
        f'</div>'
        f'<div class="resp-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px">'
        f'<div class="freq-stat"><div class="freq-stat-val" style="color:#374151">{freq["total_dias"]}</div><div class="freq-stat-lbl">Dias letivos</div></div>'
        f'<div class="freq-stat"><div class="freq-stat-val" style="color:#10B981">{freq["presencas"]}</div><div class="freq-stat-lbl">Presenças</div></div>'
        f'<div class="freq-stat"><div class="freq-stat-val" style="color:{cor}">{freq["faltas"]}</div><div class="freq-stat-lbl">Faltas</div></div>'
        f'<div class="freq-stat"><div class="freq-stat-val" style="color:#6366F1">{freq["faltas_injustificadas"]}</div><div class="freq-stat-lbl">Injustificadas</div></div>'
        f'</div>'
        f'{msg_html}'
        f'{padrao_html}'
        f'</div>'
    )
    st.markdown(card, unsafe_allow_html=True)
