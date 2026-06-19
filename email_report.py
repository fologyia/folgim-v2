"""
Módulo de envio de relatório semanal de alunos em risco por e-mail.

Configuração necessária em .streamlit/secrets.toml:
    EMAIL_REMETENTE   = "docente@gmail.com"
    EMAIL_SENHA       = "sua_senha_de_app"      # senha de app do Gmail, não a senha normal
    EMAIL_DESTINATARIO = "docente@gmail.com"    # pode ser o mesmo ou outro endereço
    EMAIL_SMTP_HOST   = "smtp.gmail.com"        # padrão Gmail; Outlook: smtp.office365.com
    EMAIL_SMTP_PORT   = 587
"""
import io
import json
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import streamlit as st

_CONTROLE_PATH = ".ia_cache/email_semanal.json"


def _carregar_controle() -> dict:
    if os.path.exists(_CONTROLE_PATH):
        with open(_CONTROLE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"ultimo_envio": None}


def _salvar_controle(ts: str) -> None:
    os.makedirs(os.path.dirname(_CONTROLE_PATH), exist_ok=True)
    with open(_CONTROLE_PATH, "w", encoding="utf-8") as f:
        json.dump({"ultimo_envio": ts}, f)


def ultimo_envio_fmt() -> str | None:
    ctrl = _carregar_controle()
    ts = ctrl.get("ultimo_envio")
    if ts:
        try:
            return datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
    return None


def deve_enviar_agora() -> bool:
    """Retorna True se for sexta-feira após 16:30 e ainda não enviou nesta sexta."""
    agora = datetime.now()

    # Só dispara nas sextas-feiras (weekday 4) após 16:30
    if agora.weekday() != 4:
        return False
    if agora.hour < 16 or (agora.hour == 16 and agora.minute < 30):
        return False

    # Verifica se já enviou hoje (esta sexta)
    ctrl = _carregar_controle()
    ts   = ctrl.get("ultimo_envio")
    if not ts:
        return True  # nunca enviou → enviar agora
    try:
        ultimo = datetime.fromisoformat(ts)
        return ultimo.date() < agora.date()  # só reenvia se o último foi antes de hoje
    except Exception:
        return True


def _html_relatorio(
    turma: str,
    perfil_df: pd.DataFrame,
    df_freq: pd.DataFrame,
    data_geracao: str,
    df_turma: pd.DataFrame = None,
    df_turmas: pd.DataFrame = None,
    df_feriados: list = None,
) -> str:
    from data.analysis import calcular_frequencia_aluno, obter_datas_validas

    criticos  = perfil_df[perfil_df["Risco"] == "critico"]
    atencao   = perfil_df[perfil_df["Risco"] == "atencao"]
    n_total   = len(perfil_df)
    n_risco   = len(criticos) + len(atencao)
    media_g   = round(perfil_df["Média"].mean(), 1) if not perfil_df.empty else 0

    aluno_turma_map = df_turma.set_index("Aluno")["Turma"].to_dict() if df_turma is not None and "Turma" in df_turma.columns else {}
    _dg_cache = {}
    def _get_dg(t):
        if t not in _dg_cache:
            _dg_cache[t] = obter_datas_validas(t, df_turmas, df_turma, df_freq, df_feriados)
        return _dg_cache[t]

    def _row_aluno(row, cor_fundo: str, emoji: str) -> str:
        t_nome = aluno_turma_map.get(row["Aluno"], turma)
        freq = calcular_frequencia_aluno(df_freq, row["Aluno"], _get_dg(t_nome))
        freq_str = f"{freq['pct_presenca']:.1f}%" if freq["tem_dados"] else "—"
        seq_f = freq.get("faltas_seq_atual", 0)
        badge_seq = (
            f'<span style="background:#7C3AED;color:white;border-radius:4px;'
            f'padding:2px 6px;font-size:11px;margin-left:6px">⛔ {seq_f} faltas seguidas</span>'
            if seq_f >= 3 else (
                f'<span style="background:#EA580C;color:white;border-radius:4px;'
                f'padding:2px 6px;font-size:11px;margin-left:6px">⚠️ {seq_f} faltas seguidas</span>'
                if seq_f >= 2 else ""
            )
        )
        return f"""
        <tr style="background:{cor_fundo}">
            <td style="padding:10px 14px;font-weight:600">{emoji} {row['Aluno']}{badge_seq}</td>
            <td style="padding:10px 14px;text-align:center;font-weight:700;color:{'#DC2626' if row['Média'] < 6 else '#D97706'}">{row['Média']:.1f}</td>
            <td style="padding:10px 14px;text-align:center">{row.get('Notas_Baixas', '—')}</td>
            <td style="padding:10px 14px;text-align:center">{freq_str}</td>
            <td style="padding:10px 14px;text-align:center;color:{'#DC2626' if row.get('Seq_Critica',0) > 0 else '#6B7280'}">{row.get('Seq_Critica', 0) or '—'}</td>
        </tr>"""

    rows_html = ""
    for _, r in criticos.iterrows():
        rows_html += _row_aluno(r, "#FFF5F5", "🔴")
    for _, r in atencao.iterrows():
        rows_html += _row_aluno(r, "#FFFBEB", "🟡")

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
          background:#F4F6F9; margin:0; padding:0; }}
  .container {{ max-width:680px; margin:32px auto; background:white;
                border-radius:16px; overflow:hidden;
                box-shadow:0 4px 24px rgba(0,0,0,0.10); }}
  .header {{ background:linear-gradient(135deg,#00539F,#0369A1);
             padding:28px 32px; color:white; }}
  .header h1 {{ margin:0 0 4px; font-size:1.5rem; font-weight:800; }}
  .header p  {{ margin:0; opacity:0.8; font-size:0.88rem; }}
  .kpi-row   {{ display:flex; gap:0; border-bottom:1px solid #E5E7EB; }}
  .kpi       {{ flex:1; padding:20px; text-align:center; border-right:1px solid #E5E7EB; }}
  .kpi:last-child {{ border-right:none; }}
  .kpi-val   {{ font-size:2rem; font-weight:800; color:#111827; }}
  .kpi-lbl   {{ font-size:0.72rem; font-weight:700; color:#9CA3AF;
                text-transform:uppercase; letter-spacing:0.06em; margin-top:2px; }}
  .section   {{ padding:24px 32px; }}
  .section h2 {{ font-size:0.78rem; font-weight:700; color:#9CA3AF;
                 text-transform:uppercase; letter-spacing:0.08em; margin:0 0 14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.86rem; }}
  th {{ background:#F9FAFB; padding:10px 14px; text-align:left;
        font-size:0.72rem; font-weight:700; color:#6B7280;
        text-transform:uppercase; letter-spacing:0.06em; border-bottom:2px solid #E5E7EB; }}
  .footer {{ background:#F9FAFB; padding:16px 32px; font-size:0.75rem;
             color:#9CA3AF; border-top:1px solid #E5E7EB; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 Relatório Semanal · {turma}</h1>
    <p>Gerado automaticamente em {data_geracao} · SENAI Painel Docente</p>
  </div>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-val">{n_total}</div><div class="kpi-lbl">Alunos</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#E30613">{n_risco}</div><div class="kpi-lbl">Em Risco</div></div>
    <div class="kpi"><div class="kpi-val">{len(criticos)}</div><div class="kpi-lbl">Críticos</div></div>
    <div class="kpi"><div class="kpi-val">{media_g}</div><div class="kpi-lbl">Média Geral</div></div>
  </div>
  {'<div class="section"><h2>⚠️ Alunos que precisam de atenção</h2><table><thead><tr><th>Aluno</th><th>Média</th><th>Notas &lt;6</th><th>Frequência</th><th>Seq. Crítica</th></tr></thead><tbody>' + rows_html + '</tbody></table></div>' if rows_html else '<div class="section" style="color:#059669;text-align:center;padding:32px"><b>✅ Nenhum aluno em situação crítica ou de atenção esta semana!</b></div>'}
  <div class="footer">
    Este relatório foi gerado automaticamente pelo <b>SENAI Painel Docente</b>.
    Para mais detalhes, acesse o sistema.
  </div>
</div>
</body>
</html>"""


def enviar_relatorio(
    turma: str,
    perfil_df: pd.DataFrame,
    df_freq: pd.DataFrame,
    df_turma: pd.DataFrame | None = None,
    df_turmas: pd.DataFrame = None,
    df_feriados: list = None,
) -> tuple[bool, str]:
    """
    Envia o relatório semanal por e-mail com PDF da turma em anexo.

    Retorna (sucesso: bool, mensagem: str).
    """
    cfg = _get_email_config()
    remetente, senha, destinatario, host, port = cfg["remetente"], cfg["senha"], cfg["destinatario"], cfg["host"], cfg["port"]

    if not all([remetente, senha, destinatario]):
        return False, (
            "Configure EMAIL_REMETENTE, EMAIL_SENHA e EMAIL_DESTINATARIO "
            "em `.streamlit/secrets.toml` ou nos Secrets do Replit."
        )

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    html_body    = _html_relatorio(turma, perfil_df, df_freq, data_geracao, df_turma, df_turmas, df_feriados)

    # Gera o PDF com o relatório COMPLETO da turma (panorama, saúde da turma,
    # alerta pedagógico, critérios sistêmicos, evolução temporal, ranking e
    # alunos que requerem atenção). As métricas de saúde são calculadas aqui,
    # sem depender do estado das telas.
    pdf_bytes: bytes | None = None
    if df_turma is not None and not perfil_df.empty:
        try:
            from data.analysis import calcular_saude_turma
            from pdf.generator import gerar_relatorio_turma_pdf
            saude = calcular_saude_turma(df_turma, perfil_df)
            pdf_bytes = gerar_relatorio_turma_pdf(
                turma=turma,
                perfil=perfil_df,
                df_turma=df_turma,
                saude=saude,
                df_freq=df_freq,
            )
        except Exception:
            # Fallback para o relatório básico se o completo falhar, para que o
            # e-mail ainda saia com algum anexo útil.
            try:
                from pdf.generator import gerar_relatorio_basico_turma_pdf
                pdf_bytes = gerar_relatorio_basico_turma_pdf(
                    turma=turma,
                    perfil_df=perfil_df,
                    df_turma=df_turma,
                    df_freq=df_freq,
                )
            except Exception:
                pdf_bytes = None  # falha silenciosa — envia e-mail sem anexo

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"[SENAI] Relatório Semanal — {turma} — {data_geracao}"
    msg["From"]    = remetente
    msg["To"]      = destinatario
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if pdf_bytes:
        nome_pdf = f"relatorio_turma_{turma.replace(' ','_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
        pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", "attachment", filename=nome_pdf)
        msg.attach(pdf_part)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(remetente, senha)
            smtp.sendmail(remetente, [destinatario], msg.as_string())
        _salvar_controle(datetime.now().isoformat())
        _anexo = " (com PDF em anexo)" if pdf_bytes else ""
        return True, f"Relatório enviado para {destinatario}{_anexo}"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Autenticação falhou. Para Gmail, use uma **Senha de App** "
            "(myaccount.google.com → Segurança → Senhas de app)."
        )
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro inesperado: {e}"


def _get_email_config() -> dict:
    """Lê configurações de e-mail de st.secrets ou variáveis de ambiente."""
    try:
        return {
            "remetente":    st.secrets.get("EMAIL_REMETENTE", "") or os.environ.get("EMAIL_REMETENTE", ""),
            "senha":        st.secrets.get("EMAIL_SENHA", "") or os.environ.get("EMAIL_SENHA", ""),
            "destinatario": st.secrets.get("EMAIL_DESTINATARIO", "") or os.environ.get("EMAIL_DESTINATARIO", ""),
            "host":         st.secrets.get("EMAIL_SMTP_HOST", "") or os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com"),
            "port":         int(st.secrets.get("EMAIL_SMTP_PORT", 0) or os.environ.get("EMAIL_SMTP_PORT", 587)),
        }
    except Exception:
        return {
            "remetente":    os.environ.get("EMAIL_REMETENTE", ""),
            "senha":        os.environ.get("EMAIL_SENHA", ""),
            "destinatario": os.environ.get("EMAIL_DESTINATARIO", ""),
            "host":         os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com"),
            "port":         int(os.environ.get("EMAIL_SMTP_PORT", 587)),
        }


def enviar_email_teste() -> tuple[bool, str]:
    """
    Envia um e-mail simples de confirmação de configuração.
    Não grava no controle de envio semanal.
    """
    cfg = _get_email_config()
    remetente, senha, destinatario, host, port = cfg["remetente"], cfg["senha"], cfg["destinatario"], cfg["host"], cfg["port"]

    if not all([remetente, senha, destinatario]):
        return False, "Configure EMAIL_REMETENTE, EMAIL_SENHA e EMAIL_DESTINATARIO em secrets.toml."

    agora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    html  = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             background:#F4F6F9;margin:0;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,0.10)">
    <div style="background:linear-gradient(135deg,#00539F,#0369A1);padding:28px 32px;color:white">
      <div style="font-size:1.5rem;font-weight:800;margin-bottom:4px">✅ E-mail configurado!</div>
      <div style="opacity:0.8;font-size:0.88rem">SENAI Painel Docente</div>
    </div>
    <div style="padding:28px 32px">
      <p style="font-size:1rem;color:#1F2937;margin:0 0 16px">
        O envio de e-mails está funcionando corretamente.
      </p>
      <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;
                  padding:14px 18px;font-size:0.88rem;color:#15803D">
        <b>📅 Agendamento ativo:</b> toda <b>sexta-feira às 16:30</b><br>
        <span style="font-size:0.82rem;color:#166534">
          O relatório com alunos em risco será enviado automaticamente.
        </span>
      </div>
      <p style="font-size:0.78rem;color:#9CA3AF;margin:20px 0 0">
        Teste enviado em {agora}
      </p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[SENAI] ✅ Teste de e-mail — configuração bem-sucedida"
    msg["From"]    = remetente
    msg["To"]      = destinatario
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(remetente, senha)
            smtp.sendmail(remetente, [destinatario], msg.as_string())
        return True, f"✅ E-mail de teste enviado para **{destinatario}**"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "❌ Autenticação falhou. Use uma **Senha de App** do Gmail, "
            "não a senha normal (myaccount.google.com → Segurança → Senhas de app)."
        )
    except smtplib.SMTPException as e:
        return False, f"❌ Erro SMTP: {e}"
    except Exception as e:
        return False, f"❌ Erro: {e}"
