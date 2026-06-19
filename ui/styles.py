from config import CORES

CSS_GLOBAL = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; color: {CORES['texto']}; }}

    section[data-testid="stSidebar"] {{
        background: linear-gradient(160deg, {CORES['azul']} 0%, #002d5a 100%);
    }}
    section[data-testid="stSidebar"] * {{ color: white !important; }}
    section[data-testid="stSidebar"] .stSelectbox > div > div {{
        background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25); border-radius: 8px;
    }}
    section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.2) !important; }}
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stButton button p,
    section[data-testid="stSidebar"] .stButton button * {{
        color: #1F2937 !important;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        background: white !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stButton button:hover p,
    section[data-testid="stSidebar"] .stButton button:hover * {{
        color: #111827 !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background: rgba(255,255,255,0.9) !important;
        border-color: white !important;
    }}
    section[data-testid="stSidebar"] .stMultiSelect > div > div {{
        background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;
    }}

    .header-wrapper {{
        background: linear-gradient(135deg, {CORES['azul']} 0%, #003d7a 55%, {CORES['vermelho']} 100%);
        border-radius: 20px; padding: 30px 40px; margin-bottom: 30px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 10px 40px rgba(0,83,159,0.3);
        position: relative; overflow: hidden;
    }}
    .header-wrapper::before {{
        content: ''; position: absolute; top: -50%; right: -5%;
        width: 300px; height: 300px; border-radius: 50%;
        background: rgba(255,255,255,0.04); pointer-events: none;
    }}
    .header-title {{ font-family: 'Montserrat', sans-serif; font-size: 1.8rem;
        font-weight: 800; color: white; margin: 0; letter-spacing: -0.02em; }}
    .header-sub {{ font-size: 0.87rem; color: rgba(255,255,255,0.7); margin-top: 5px; }}
    .header-badge {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
        backdrop-filter: blur(4px);
        border-radius: 50px; padding: 6px 16px; font-size: 0.78rem; color: white; font-weight: 500; }}

    .kpi-card {{ background: white; border-radius: 16px; padding: 22px 24px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.06); border-top: 4px solid {CORES['azul']};
        transition: transform 0.2s ease, box-shadow 0.2s ease; height: 100%;
        position: relative; overflow: hidden; }}
    .kpi-card::after {{
        content: ''; position: absolute; bottom: -20px; right: -20px;
        width: 80px; height: 80px; border-radius: 50%;
        background: rgba(0,83,159,0.04); pointer-events: none;
    }}
    .kpi-card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
    .kpi-card.danger  {{ border-top-color: {CORES['vermelho']}; }}
    .kpi-card.danger::after {{ background: rgba(227,6,19,0.04); }}
    .kpi-card.success {{ border-top-color: {CORES['verde']}; }}
    .kpi-card.success::after {{ background: rgba(16,185,129,0.04); }}
    .kpi-card.warning {{ border-top-color: {CORES['amarelo']}; }}
    .kpi-label {{ font-size: 0.70rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.1em; color: #6B7280; margin-bottom: 10px; }}
    .kpi-value {{ font-family: 'Montserrat', sans-serif; font-size: 2.2rem;
        font-weight: 800; color: {CORES['texto']}; line-height: 1; }}
    .kpi-desc {{ font-size: 0.78rem; color: #9CA3AF; margin-top: 8px; }}

    .section-title {{ font-family: 'Montserrat', sans-serif; font-size: 1.0rem; font-weight: 700;
        color: {CORES['texto']}; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }}
    .section-title::after {{ content: ''; flex: 1; height: 2px;
        background: linear-gradient(90deg, {CORES['azul']}25, transparent); border-radius: 2px; }}

    .alert-item {{ background: #FFF5F5; border-left: 4px solid {CORES['vermelho']};
        border-radius: 0 12px 12px 0; padding: 14px 18px; margin-bottom: 10px;
        display: flex; align-items: center; gap: 14px;
        transition: transform 0.15s ease; }}
    .alert-item:hover {{ transform: translateX(3px); }}
    .alert-nota {{ font-family: 'Montserrat'; font-size: 1.45rem; font-weight: 800;
        color: {CORES['vermelho']}; min-width: 52px; text-align: center; }}
    .alert-info span {{ font-size: 0.8rem; color: #6B7280; }}
    .alert-info strong {{ display: block; font-size: 0.92rem; color: {CORES['texto']}; }}

    .sequencia-critica {{
        background: linear-gradient(135deg, #7F1D1D, #B91C1C);
        border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;
        display: flex; align-items: center; gap: 18px;
        box-shadow: 0 6px 24px rgba(127,29,29,0.4);
        animation: pulso 2s ease-in-out infinite;
    }}
    @keyframes pulso {{
        0%, 100% {{ box-shadow: 0 6px 24px rgba(127,29,29,0.4); }}
        50%       {{ box-shadow: 0 6px 36px rgba(127,29,29,0.7); }}
    }}
    .sequencia-icone {{ font-size: 2.2rem; }}
    .sequencia-texto {{ color: white; }}
    .sequencia-texto strong {{ font-family: Montserrat; font-size: 1.05rem; display: block; }}
    .sequencia-texto span   {{ font-size: 0.82rem; opacity: 0.85; }}

    .rec-item {{ background: #FFFBEB; border-left: 4px solid {CORES['amarelo']};
        border-radius: 0 12px 12px 0; padding: 14px 18px; margin-bottom: 10px;
        display: flex; align-items: center; gap: 14px; }}
    .obs-card {{ background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 14px;
        padding: 18px 22px; margin-bottom: 14px; }}
    .obs-card p {{ font-size: 0.88rem; color: #0369A1; margin: 0; font-style: italic; line-height: 1.6; }}
    .obs-card span {{ font-size: 0.75rem; color: #64748B; display: block; margin-bottom: 6px; font-weight: 600; }}

    .divider {{ height: 1px; background: linear-gradient(90deg, transparent, #E5E7EB 30%, #E5E7EB 70%, transparent);
        margin: 32px 0; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    /* Sidebar sempre aberta — esconde todos os botões de colapso */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button,
    button[data-testid="baseButton-headerNoPadding"],
    button[data-testid="baseButton-header"],
    section[data-testid="stSidebar"] > div:first-child > div > button,
    section[data-testid="stSidebar"] button[kind="header"],
    section[data-testid="stSidebarHeader"] button {{
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }}
    .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

    .risco-card {{ background: white; border-radius: 14px; padding: 16px 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06); border-left: 5px solid #E5E7EB;
        display: flex; align-items: center; gap: 14px;
        transition: transform 0.15s ease, box-shadow 0.15s ease; }}
    .risco-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }}
    .risco-card.critico  {{ border-left-color: {CORES['vermelho']}; background: #FFF8F8; }}
    .risco-card.atencao  {{ border-left-color: {CORES['amarelo']};  background: #FFFDF0; }}
    .risco-card.adequado {{ border-left-color: {CORES['verde']};    background: #F0FDF8; }}
    .risco-card.excelente{{ border-left-color: {CORES['roxo']};     background: #F5F3FF; }}
    .semaforo {{ width: 40px; height: 40px; border-radius: 50%; display:flex;
        align-items:center; justify-content:center; font-size: 1.15rem; flex-shrink:0; }}
    .semaforo.critico  {{ background: #FEE2E2; }}
    .semaforo.atencao  {{ background: #FEF9C3; }}
    .semaforo.adequado {{ background: #D1FAE5; }}
    .semaforo.excelente{{ background: #EDE9FE; }}
    .risco-nome {{ font-weight: 700; font-size: 0.86rem; color: {CORES['texto']}; line-height: 1.3; }}
    .risco-meta {{ font-size: 0.72rem; color: #6B7280; margin-top: 3px; }}
    .risco-nota {{ font-family: Montserrat,sans-serif; font-size: 1.4rem; font-weight: 800;
        min-width: 44px; text-align: right; margin-left: auto; }}
    .risco-nota.critico  {{ color: {CORES['vermelho']}; }}
    .risco-nota.atencao  {{ color: #B45309; }}
    .risco-nota.adequado {{ color: {CORES['verde']}; }}
    .risco-nota.excelente{{ color: {CORES['roxo']}; }}

    .diag-card {{ background: linear-gradient(135deg,#EBF4FF 0%,#F0F9FF 100%);
        border: 1px solid #BAE6FD; border-radius: 16px; padding: 24px 28px;
        margin-bottom: 26px; position: relative; overflow: hidden; }}
    .diag-card::before {{ content:''; position:absolute; top:0; left:0; width:5px;
        height:100%; background: linear-gradient(180deg,{CORES['azul']},{CORES['verde']}); border-radius:5px 0 0 5px; }}
    .diag-icon {{ font-size: 1.6rem; margin-bottom: 10px; }}
    .diag-titulo {{ font-family:Montserrat,sans-serif; font-weight:700; font-size:0.85rem;
        color:{CORES['azul']}; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .diag-texto {{ font-size: 0.9rem; color: #1E3A5F; line-height: 1.75; }}
    .diag-tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
    .diag-tag {{ padding: 5px 13px; border-radius: 50px; font-size: 0.72rem;
        font-weight: 600; letter-spacing: 0.04em; }}
    .diag-tag.positivo {{ background:#D1FAE5; color:#065F46; }}
    .diag-tag.negativo {{ background:#FEE2E2; color:#991B1B; }}
    .diag-tag.neutro   {{ background:#E0E7FF; color:#3730A3; }}

    .turma-header {{ background: linear-gradient(135deg,#1E3A5F 0%,{CORES['azul']} 55%,#0369A1 100%);
        border-radius:20px; padding:32px 40px; margin-bottom:30px;
        box-shadow: 0 10px 40px rgba(0,83,159,0.3); position: relative; overflow: hidden; }}
    .turma-header::before {{
        content:''; position:absolute; bottom:-60px; right:-40px;
        width:260px; height:260px; border-radius:50%;
        background:rgba(255,255,255,0.04); pointer-events:none;
    }}
    .turma-stat {{ background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.2);
        backdrop-filter:blur(4px);
        border-radius:14px; padding:18px 22px; text-align:center; }}
    .turma-stat-val {{ font-family:Montserrat,sans-serif; font-size:2rem; font-weight:800; color:white; }}
    .turma-stat-lbl {{ font-size:0.72rem; color:rgba(255,255,255,0.7); margin-top:4px;
        text-transform:uppercase; letter-spacing:0.1em; }}

    .ia-chat-bubble {{
        background: white; border-radius: 14px; padding: 20px 26px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.07); margin-bottom: 18px;
        border-left: 4px solid {CORES['roxo']};
    }}
    .ia-header {{
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #9333EA 100%);
        border-radius: 20px; padding: 36px; margin-bottom: 30px;
        color: white; text-align: center;
        box-shadow: 0 12px 40px rgba(139, 92, 246, 0.35);
        position: relative; overflow: hidden;
    }}
    .ia-header::before {{
        content:''; position:absolute; top:-80px; right:-80px;
        width:280px; height:280px; border-radius:50%;
        background:rgba(255,255,255,0.05); pointer-events:none;
    }}
    .ia-student-card {{
        background: #F9FAFB; border: 1.5px solid #E5E7EB; border-radius: 12px;
        padding: 16px 18px; margin-bottom: 10px; transition: all 0.2s;
    }}
    .ia-student-card:hover {{ border-color: {CORES['roxo']}; background: white; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}

    @keyframes fadeUp {{
        from {{ opacity:0; transform:translateY(12px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}
    .iif-tooltip-wrap {{ position:relative; display:inline-block; margin-left:8px; vertical-align:middle; cursor:pointer; }}
    .iif-tooltip-icon {{ display:inline-flex; align-items:center; justify-content:center;
        width:16px; height:16px; border-radius:50%; background:#E0E7FF; color:#4F46E5;
        font-size:0.65rem; font-weight:800; font-style:normal; line-height:1;
        transition: background 0.2s; }}
    .iif-tooltip-wrap:hover .iif-tooltip-icon {{ background:#4F46E5; color:white; }}
    .iif-tooltip-box {{ display:none; position:absolute; bottom:calc(100% + 10px); left:50%;
        transform:translateX(-50%); background:#1E293B; color:#F1F5F9;
        border-radius:12px; padding:16px 18px; width:300px; font-size:0.78rem;
        line-height:1.65; font-family:sans-serif; font-weight:400;
        box-shadow:0 8px 32px rgba(0,0,0,0.25); z-index:9999;
        pointer-events:none; white-space:normal; text-align:left; }}
    .iif-tooltip-box b {{ color:#A5B4FC; }}
    .iif-tooltip-box::after {{ content:''; position:absolute; top:100%; left:50%;
        transform:translateX(-50%); border:6px solid transparent;
        border-top-color:#1E293B; }}
    .iif-tooltip-wrap:hover .iif-tooltip-box {{ display:block; }}
    .kpi-card {{ animation: fadeUp 0.35s ease both; }}

    .freq-card {{ background: white; border-radius: 16px; padding: 22px 26px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.06); margin-bottom: 20px;
        border-left: 5px solid #6366F1; }}
    .freq-card.verde  {{ border-left-color: #10B981; }}
    .freq-card.amarelo{{ border-left-color: #F59E0B; }}
    .freq-card.vermelho{{ border-left-color: #E30613; }}
    .freq-barra-bg {{ background:#E5E7EB; border-radius:50px; height:10px; overflow:hidden; }}
    .freq-barra-fill {{ height:10px; border-radius:50px; transition: width 0.4s ease; }}
    .freq-stat {{ background:#F8FAFC; border-radius:10px; padding:12px 14px; text-align:center; }}
    .freq-stat-val {{ font-family:Montserrat,sans-serif; font-size:1.4rem; font-weight:800; }}
    .freq-stat-lbl {{ font-size:0.68rem; color:#6B7280; text-transform:uppercase;
        letter-spacing:0.08em; margin-top:3px; font-weight:600; }}
    .freq-alerta {{ background:#FFF5F5; border:1px solid #FECACA; border-radius:10px;
        padding:10px 14px; margin-top:12px; font-size:0.82rem; color:#991B1B; }}
    .freq-ok {{ background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px;
        padding:10px 14px; margin-top:12px; font-size:0.82rem; color:#166534; }}

    .apple-header {{
        background: rgba(255,255,255,0.9);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid #E5E5EA;
        padding: 20px 28px 18px;
        margin: -1.5rem -1rem 24px;
    }}
    .apple-kpi {{
        background: white;
        border-radius: 16px;
        padding: 20px 22px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
        height: 100%;
    }}
    .apple-card {{
        background: white;
        border-radius: 16px;
        padding: 22px 26px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }}
    .apple-label {{
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8E8E93;
        margin-bottom: 8px;
    }}
    .apple-value {{
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -0.02em;
        line-height: 1;
    }}
    .apple-alert-item {{
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 14px;
        background: #FFF5F5;
        border-radius: 10px;
        border-left: 3px solid #FF3B30;
        margin-bottom: 8px;
    }}
    .apple-badge {{
        background: #FF3B30;
        color: white;
        font-size: 10px;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 50px;
    }}
    .apple-vetor-card {{
        background: #F5F5F7;
        border-radius: 12px;
        padding: 16px 18px;
    }}
    .apple-stat-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #F2F2F7;
    }}
    .apple-freq-dot {{
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        text-align: center;
    }}

    /* ═══════════════════════════════════════════════════════════════════
       RESPONSIVIDADE MOBILE — só afeta telas ≤768px; desktop intacto
       ═══════════════════════════════════════════════════════════════════ */
    @media (max-width: 768px) {{
        /* Reabilitar colapso da sidebar em telas pequenas (sobrepõe a regra global) */
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapseButton"] button,
        button[data-testid="baseButton-headerNoPadding"],
        button[data-testid="baseButton-header"],
        section[data-testid="stSidebar"] > div:first-child > div > button,
        section[data-testid="stSidebar"] button[kind="header"],
        section[data-testid="stSidebarHeader"] button {{
            display: flex !important;
            visibility: visible !important;
            pointer-events: auto !important;
        }}

        /* Evitar rolagem horizontal e reduzir respiro lateral */
        [data-testid="stAppViewContainer"] {{ overflow-x: hidden; }}
        .block-container {{ padding-left: 0.9rem !important; padding-right: 0.9rem !important; }}

        /* Empilhar colunas do Streamlit em largura total */
        [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }}

        /* Grades fixas (KPIs, saúde, frequência, conteúdos didáticos) → 2 colunas */
        .resp-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}

        /* Cabeçalhos largos: empilhar conteúdo e reduzir padding */
        .header-wrapper {{ flex-direction: column; align-items: flex-start; gap: 14px; padding: 22px 24px; }}
        .header-title {{ font-size: 1.4rem; }}
        .turma-header {{ padding: 24px 22px; }}
        .ia-header {{ padding: 26px 22px; }}
        .apple-header {{ margin: -1.5rem -0.9rem 20px; padding: 16px 18px 14px; }}
    }}

    @media (max-width: 480px) {{
        /* Telas de celular muito estreitas → 1 coluna */
        .resp-grid {{ grid-template-columns: 1fr !important; }}
        .header-title {{ font-size: 1.2rem; }}
        .turma-stat-val {{ font-size: 1.6rem; }}
        .apple-value {{ font-size: 28px; }}
        .kpi-value {{ font-size: 1.7rem; }}
    }}
</style>
"""
