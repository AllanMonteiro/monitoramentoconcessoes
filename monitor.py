#!/usr/bin/env python3
"""
Monitor de Concessões Florestais
Rastreia atualizações nos sites do SFB e IDEFLOR-Bio.
Executa via GitHub Actions todo dia às 08h e 16h (horário de Brasília).
"""

import json
import os
import re
import smtplib
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── URLS MONITORADAS ──────────────────────────────────────────────────────────
TARGETS = [
    {
        "id": "sfb_licitacao",
        "nome": "SFB — Editais em Licitação",
        "url": "https://www.gov.br/florestal/pt-br/assuntos/concessoes-e-monitoramento/editais-em-licitacao",
        "orgao": "SFB",
    },
    {
        "id": "sfb_balata",
        "nome": "SFB — Flona Balata-Tufari",
        "url": "https://www.gov.br/florestal/pt-br/assuntos/concessoes-e-monitoramento/editais-em-consulta-publica/floresta-nacional-de-balata-tufari",
        "orgao": "SFB",
    },
    {
        "id": "sfb_castanho",
        "nome": "SFB — Gleba Castanho",
        "url": "https://www.gov.br/florestal/pt-br/assuntos/concessoes-e-monitoramento/editais-em-licitacao/gleba-castanho-am",
        "orgao": "SFB",
    },
    {
        "id": "sfb_proximo",
        "nome": "SFB — Próximos Editais",
        "url": "https://www.gov.br/florestal/pt-br/assuntos/concessoes-e-monitoramento/proximos-editais",
        "orgao": "SFB",
    },
    {
        "id": "sfb_iquiri",
        "nome": "SFB — Flona do Iquiri",
        "url": "https://www.gov.br/florestal/pt-br/assuntos/concessoes-e-monitoramento/editais-em-consulta-publica/floresta-nacional-do-iquiri",
        "orgao": "SFB",
    },
    {
        "id": "ideflor_licitacoes",
        "nome": "IDEFLOR-Bio — Licitações e Contratos",
        "url": "https://ideflorbio.pa.gov.br/licitacoes-e-contratos/",
        "orgao": "IDEFLOR-Bio",
    },
    {
        "id": "ideflor_paru_iriri",
        "nome": "IDEFLOR-Bio — CP 001/2026 Paru e Iriri",
        "url": "https://ideflorbio.pa.gov.br/paru-iriri-edital-aberto",
        "orgao": "IDEFLOR-Bio",
    },
    {
        "id": "ideflor_paof",
        "nome": "IDEFLOR-Bio — PAOF",
        "url": "https://ideflorbio.pa.gov.br/paof/",
        "orgao": "IDEFLOR-Bio",
    },
]

STATE_FILE = Path("monitor_state.json")
REPORT_FILE = Path("monitor_report.json")
BRT = timezone(timedelta(hours=-3))


# ── FUNÇÕES ───────────────────────────────────────────────────────────────────

def fetch_page(url: str, timeout: int = 20) -> str | None:
    """Baixa o HTML de uma URL e retorna como string."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MonitorConcessoes/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        print(f"  ⚠ Erro ao acessar {url}: {e}")
        return None


def extract_fingerprint(html: str) -> dict:
    """
    Extrai sinais relevantes do HTML para detectar mudanças reais.
    Ignora timestamps de acesso e elementos dinâmicos sem conteúdo.
    """
    # Remove scripts e estilos
    clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL)
    clean = re.sub(r"<!--.*?-->", "", clean, flags=re.DOTALL)
    # Remove atributos de sessão e tokens dinâmicos
    clean = re.sub(r'(csrf|token|nonce|_=)["\s]*[^\s"&>]+', "", clean, flags=re.I)

    # Extrai datas de modificação mencionadas no texto
    dates = re.findall(
        r"Modificado em (\d{2}/\d{2}/\d{4})|"
        r"Publicado em (\d{2}/\d{2}/\d{4})|"
        r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2})",
        clean,
    )
    dates_flat = [d for group in dates for d in group if d]

    # Extrai links PDF (indicam novos documentos)
    pdfs = sorted(set(re.findall(r'href="([^"]+\.pdf[^"]*)"', clean, re.I)))

    # Hash do conteúdo limpo (sem whitespace redundante)
    body = re.sub(r"\s+", " ", clean).strip()
    content_hash = hashlib.sha256(body.encode()).hexdigest()[:16]

    return {
        "hash": content_hash,
        "dates": dates_flat[:10],  # até 10 datas
        "pdfs": pdfs[:30],         # até 30 PDFs
        "length": len(body),
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def check_all() -> list[dict]:
    """Verifica todas as URLs e retorna lista de mudanças detectadas."""
    state = load_state()
    changes = []
    now = datetime.now(BRT).isoformat()

    for target in TARGETS:
        uid = target["id"]
        url = target["url"]
        nome = target["nome"]
        print(f"\n🔍 Verificando: {nome}")

        html = fetch_page(url)
        if html is None:
            print("  ↳ Sem resposta — pulando")
            continue

        fp = extract_fingerprint(html)
        prev = state.get(uid, {})

        mudancas = []

        # Detecta mudança de hash (conteúdo geral)
        if prev.get("hash") and prev["hash"] != fp["hash"]:
            mudancas.append("Conteúdo da página alterado")

        # Detecta novos PDFs
        prev_pdfs = set(prev.get("pdfs", []))
        new_pdfs = set(fp["pdfs"]) - prev_pdfs
        if new_pdfs:
            mudancas.append(f"Novos PDFs detectados: {len(new_pdfs)}")
            for pdf in sorted(new_pdfs)[:5]:
                mudancas.append(f"  → {pdf}")

        # Detecta novas datas
        prev_dates = set(prev.get("dates", []))
        new_dates = set(fp["dates"]) - prev_dates
        if new_dates:
            mudancas.append(f"Novas datas encontradas: {', '.join(sorted(new_dates))}")

        if mudancas:
            print(f"  🚨 MUDANÇA DETECTADA!")
            for m in mudancas:
                print(f"     {m}")
            changes.append({
                "id": uid,
                "nome": nome,
                "orgao": target["orgao"],
                "url": url,
                "mudancas": mudancas,
                "detectado_em": now,
                "hash_anterior": prev.get("hash", "—"),
                "hash_atual": fp["hash"],
            })
        else:
            print(f"  ✓ Sem mudanças (hash: {fp['hash']})")

        # Atualiza estado
        state[uid] = {**fp, "ultima_verificacao": now, "url": url}

    save_state(state)
    return changes


def build_email_html(changes: list[dict]) -> str:
    now_str = datetime.now(BRT).strftime("%d/%m/%Y %H:%M") + " (BRT)"
    rows = ""
    for c in changes:
        items = "".join(f"<li>{m}</li>" for m in c["mudancas"])
        rows += f"""
        <div style="border:1px solid #b8dfc8;border-left:4px solid #1d5c35;
                    background:#edf7f1;padding:14px 18px;margin-bottom:14px;border-radius:4px">
          <div style="font-weight:700;font-size:15px;color:#1d5c35">{c['nome']}</div>
          <div style="font-size:12px;color:#5a7a62;margin:3px 0 8px">
            {c['orgao']} · <a href="{c['url']}" style="color:#1d5c35">{c['url']}</a>
          </div>
          <ul style="margin:0;padding-left:18px;font-size:13px;color:#2e4a34">{items}</ul>
          <div style="font-size:11px;color:#8aaa90;margin-top:8px">
            Detectado em: {c['detectado_em']}
          </div>
        </div>"""

    return f"""
    <html><body style="font-family:sans-serif;background:#f4f7f5;padding:20px">
      <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)">
        <div style="background:#1d5c35;padding:20px 24px">
          <div style="font-size:18px;font-weight:700;color:#fff">🌲 Monitor de Concessões Florestais</div>
          <div style="font-size:12px;color:#a8dfc8;margin-top:4px">{now_str}</div>
        </div>
        <div style="padding:20px 24px">
          <p style="color:#2e4a34;margin-bottom:16px">
            <strong>{len(changes)} atualização(ões)</strong> detectada(s) nos sites monitorados:
          </p>
          {rows}
          <hr style="border:none;border-top:1px solid #e0dbd0;margin:16px 0">
          <p style="font-size:11px;color:#8aaa90;margin:0">
            Monitor automático — GitHub Actions · SFB + IDEFLOR-Bio
          </p>
        </div>
      </div>
    </body></html>"""


def send_email(changes: list[dict]):
    """Envia e-mail de alerta via Gmail SMTP."""
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    email_to  = os.environ.get("ALERT_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("\n⚠ SMTP não configurado — pulando envio de e-mail.")
        print("  Configure SMTP_USER, SMTP_PASS e ALERT_EMAIL nos Secrets do GitHub.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Monitor Florestal — {len(changes)} atualização(ões) detectada(s)"
    msg["From"]    = smtp_user
    msg["To"]      = email_to

    # Texto simples
    txt = f"Monitor de Concessões Florestais — {len(changes)} mudança(s):\n\n"
    for c in changes:
        txt += f"• {c['nome']}\n  {c['url']}\n"
        for m in c["mudancas"]:
            txt += f"  - {m}\n"
        txt += "\n"
    msg.attach(MIMEText(txt, "plain", "utf-8"))
    msg.attach(MIMEText(build_email_html(changes), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, email_to, msg.as_string())
        print(f"\n✅ E-mail enviado para {email_to}")
    except Exception as e:
        print(f"\n❌ Erro ao enviar e-mail: {e}")


def save_report(changes: list[dict]):
    """Salva relatório JSON para o workflow do GitHub Actions."""
    report = {
        "verificado_em": datetime.now(BRT).isoformat(),
        "total_mudancas": len(changes),
        "mudancas": changes,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n📄 Relatório salvo em {REPORT_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(f"🌲 Monitor de Concessões Florestais")
    print(f"   {datetime.now(BRT).strftime('%d/%m/%Y %H:%M')} (Brasília)")
    print(f"   {len(TARGETS)} URLs monitoradas")
    print("=" * 60)

    changes = check_all()

    print("\n" + "=" * 60)
    if changes:
        print(f"🚨 {len(changes)} MUDANÇA(S) DETECTADA(S)!")
        send_email(changes)
    else:
        print("✅ Nenhuma mudança detectada.")
    print("=" * 60)

    save_report(changes)
