from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm

_C = {
    "azul":       colors.HexColor("#00539F"),
    "azul_esc":   colors.HexColor("#003d7a"),
    "azul_claro": colors.HexColor("#EBF4FF"),
    "azul_med":   colors.HexColor("#DBEAFE"),
    "verm":       colors.HexColor("#E30613"),
    "verm_claro": colors.HexColor("#FFF0F0"),
    "verde":      colors.HexColor("#059669"),
    "verde_claro":colors.HexColor("#ECFDF5"),
    "verde_med":  colors.HexColor("#D1FAE5"),
    "amarelo":    colors.HexColor("#F59E0B"),
    "amar_claro": colors.HexColor("#FFFBEB"),
    "amar_med":   colors.HexColor("#FDE68A"),
    "roxo":       colors.HexColor("#7C3AED"),
    "roxo_claro": colors.HexColor("#F5F3FF"),
    "cinza":      colors.HexColor("#F8FAFC"),
    "cinza2":     colors.HexColor("#E2E8F0"),
    "cinza3":     colors.HexColor("#94A3B8"),
    "cinza4":     colors.HexColor("#64748B"),
    "texto":      colors.HexColor("#0F172A"),
    "texto2":     colors.HexColor("#475569"),
    "branco":     colors.white,
}

_MARGEM  = 1.8 * cm
_LARGURA = A4[0] - 2 * _MARGEM   # ≈ 17 cm

_ST = getSampleStyleSheet()
_PS_CACHE: dict[str, ParagraphStyle] = {}


def _ps(name: str, **kw) -> ParagraphStyle:
    """Cria ou reutiliza um ParagraphStyle, evitando KeyError no ReportLab ao re-gerar PDFs."""
    if name not in _PS_CACHE:
        base = kw.pop("parent", _ST["Normal"])
        try:
            _PS_CACHE[name] = ParagraphStyle(f"_pdf_{name}", parent=base, **kw)
        except KeyError:
            _PS_CACHE[name] = ParagraphStyle(f"_pdf_{name}_v2", parent=base, **kw)
    return _PS_CACHE[name]


# Estilos globais de parágrafo
_S_TITULO    = _ps("titulo",    fontName="Helvetica-Bold",  fontSize=14, textColor=_C["azul"],   spaceAfter=2)
_S_SUBTIT    = _ps("subtit",    fontName="Helvetica",       fontSize=9,  textColor=_C["texto2"], spaceAfter=0)
_S_SEC       = _ps("sec",       fontName="Helvetica-Bold",  fontSize=9,  textColor=_C["branco"], spaceAfter=0, spaceBefore=0)
_S_BODY      = _ps("body",      fontName="Helvetica",       fontSize=8,  textColor=_C["texto"],  leading=11)
_S_BODY_C    = _ps("body_c",    fontName="Helvetica",       fontSize=8,  textColor=_C["texto"],  leading=11, alignment=TA_CENTER)
_S_BOLD_C    = _ps("bold_c",    fontName="Helvetica-Bold",  fontSize=8,  textColor=_C["texto"],  leading=11, alignment=TA_CENTER)
_S_KPI_VAL   = _ps("kpi_val",   fontName="Helvetica-Bold",  fontSize=19, leading=22, alignment=TA_CENTER)
_S_KPI_LBL   = _ps("kpi_lbl",   fontName="Helvetica",       fontSize=7,  textColor=_C["texto2"], leading=9,  alignment=TA_CENTER)
_S_FOOT      = _ps("foot",      fontName="Helvetica",       fontSize=7,  textColor=_C["cinza3"], alignment=TA_CENTER)
_S_OBS       = _ps("obs",       fontName="Helvetica-Oblique", fontSize=7, textColor=_C["texto2"], leading=10)
_S_DIAG      = _ps("diag",      fontName="Helvetica",       fontSize=8,  textColor=_C["texto"],  leading=12)
_S_DIAG_TIT  = _ps("diag_tit",  fontName="Helvetica-Bold",  fontSize=8,  textColor=_C["azul"],   leading=11)
_S_REC_LABEL = _ps("rec_label", fontName="Helvetica",       fontSize=7.5,textColor=_C["cinza4"], leading=10, alignment=TA_CENTER)
_S_REC_VAL   = _ps("rec_val",   fontName="Helvetica-Bold",  fontSize=14, textColor=_C["texto"],  leading=17, alignment=TA_CENTER)
_S_CAPA_NOME = _ps("capa_nome", fontName="Helvetica-Bold",  fontSize=18, textColor=_C["azul"],   leading=24)
_S_CAPA_DT   = _ps("capa_dt",   fontName="Helvetica",       fontSize=8,  textColor=_C["texto2"], leading=12, alignment=TA_RIGHT)
_S_ALERTA_IN = _ps("alerta_in", fontName="Helvetica-Bold",  fontSize=9,  textColor=_C["branco"], leading=13)
_S_LEG       = _ps("leg",       fontName="Helvetica",       fontSize=6.5,textColor=_C["texto2"], leading=9)
_S_LEG2      = _ps("leg2",      fontName="Helvetica",       fontSize=6.5,textColor=_C["texto2"], leading=9)
_S_LEG3      = _ps("leg3",      fontName="Helvetica",       fontSize=7,  textColor=_C["texto2"], alignment=TA_CENTER, leading=10)
_S_REC_OBS   = _ps("rec_obs",   fontName="Helvetica-Oblique", fontSize=7.5, textColor=_C["texto2"], leading=10)
_S_RECOM     = _ps("recom",     fontName="Helvetica",       fontSize=8,  textColor=_C["texto"],  leading=12)
_S_RECOM_TIT = _ps("recom_tit", fontName="Helvetica-Bold",  fontSize=8,  textColor=_C["branco"], leading=12)
