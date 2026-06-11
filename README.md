# Monitor de Concessões Florestais

Site estático + monitoramento automático de atualizações nos sites do **SFB** e **IDEFLOR-Bio**.

---

## Como publicar no GitHub Pages

1. Crie um repositório público no GitHub (ex: `concessoes-florestais`)
2. Faça upload de **todos os arquivos** desta pasta mantendo a estrutura:
   ```
   index.html
   monitor.py
   monitor_state.json   ← criado automaticamente na 1ª execução
   .github/
     workflows/
       monitor.yml
   ```
3. Vá em **Settings → Pages → Source → Deploy from branch → main / root**
4. Site disponível em: `https://SEU-USUARIO.github.io/concessoes-florestais`

---

## Configurar alertas por e-mail

O monitor usa Gmail para enviar alertas. Configure os **Secrets** no GitHub:

1. Acesse: **Settings → Secrets and variables → Actions → New repository secret**

| Nome do Secret | Valor |
|---|---|
| `SMTP_USER` | seu e-mail Gmail (ex: `seuemail@gmail.com`) |
| `SMTP_PASS` | [Senha de app do Google](https://myaccount.google.com/apppasswords) ← **não é a senha normal** |
| `ALERT_EMAIL` | e-mail que receberá os alertas (pode ser o mesmo) |

> **Senha de app:** Acesse myaccount.google.com → Segurança → Verificação em 2 etapas → Senhas de app → gerar uma para "E-mail / Windows".

---

## Sites monitorados

| Site | URL |
|---|---|
| SFB — Editais em Licitação | gov.br/florestal/.../editais-em-licitacao |
| SFB — Flona Balata-Tufari | gov.br/florestal/.../balata-tufari |
| SFB — Gleba Castanho | gov.br/florestal/.../gleba-castanho-am |
| SFB — Próximos Editais | gov.br/florestal/.../proximos-editais |
| SFB — Flona do Iquiri | gov.br/florestal/.../floresta-nacional-do-iquiri |
| IDEFLOR-Bio — Licitações | ideflorbio.pa.gov.br/licitacoes-e-contratos/ |
| IDEFLOR-Bio — CP 001/2026 | ideflorbio.pa.gov.br/paru-iriri-edital-aberto |
| IDEFLOR-Bio — PAOF | ideflorbio.pa.gov.br/paof/ |

---

## Frequência

O monitor roda **automaticamente 2x por dia**:
- **08h** (horário de Brasília)
- **17h** (horário de Brasília)

Você também pode rodar manualmente: **GitHub → Actions → Monitor Concessões Florestais → Run workflow**.

---

## O que o monitor detecta

- ✅ Mudança de conteúdo (hash da página)
- ✅ Novos arquivos PDF publicados (editais, atas, DOEs)
- ✅ Novas datas de modificação no texto
- ✅ Alteração no volume de conteúdo

Quando detecta mudança → envia **e-mail de alerta** com detalhes da alteração e link direto para a página.
