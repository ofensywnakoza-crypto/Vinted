import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


# ------------------------------------------------------------------ #
# HTML template
# ------------------------------------------------------------------ #

def _item_rows(items: list[dict], color: str) -> str:
    if not items:
        return ""
    rows = ""
    for item in items:
        tips = "<br>".join(f"• {t}" for t in item["wskazowki"])
        rows += f"""
        <tr>
          <td style="padding:10px 12px; border-bottom:1px solid #eee;">
            <a href="{item['url']}" style="color:#2d3748; font-weight:600; text-decoration:none;">
              {item['tytul']}
            </a><br>
            <span style="color:#718096; font-size:13px;">
              💰 {item['cena']:.0f} zł &nbsp;|&nbsp;
              📅 {item['dni_na_rynku']} dni &nbsp;|&nbsp;
              👁 {item['wyswietlen']} wyśw. &nbsp;|&nbsp;
              ❤️ {item['polubionych']} pol.
            </span>
          </td>
          <td style="padding:10px 12px; border-bottom:1px solid #eee; color:#4a5568; font-size:13px; background:{color};">
            {tips}
          </td>
        </tr>"""
    return rows


def build_html(items: list[dict], stats: dict, login: str = "Użytkowniku") -> str:
    urgent = [i for i in items if i["priorytet"] == "wysoki"]
    medium = [i for i in items if i["priorytet"] == "sredni"]
    ok     = [i for i in items if i["priorytet"] == "niski"]
    now    = datetime.now().strftime("%d.%m.%Y o %H:%M")

    urgent_section = ""
    if urgent:
        rows = _item_rows(urgent, "#fff5f5")
        urgent_section = f"""
        <h2 style="color:#c53030; font-size:16px; margin:28px 0 8px;">
          🔴 Pilne — działaj teraz ({len(urgent)})
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse; border:1px solid #fed7d7; border-radius:8px; overflow:hidden;">
          <thead>
            <tr style="background:#fff5f5;">
              <th style="padding:8px 12px; text-align:left; font-size:13px; color:#c53030;">Ogłoszenie</th>
              <th style="padding:8px 12px; text-align:left; font-size:13px; color:#c53030;">Co zrobić</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    medium_section = ""
    if medium:
        rows = _item_rows(medium, "#fffff0")
        medium_section = f"""
        <h2 style="color:#b7791f; font-size:16px; margin:28px 0 8px;">
          🟡 Warto się przyjrzeć ({len(medium)})
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse; border:1px solid #faf089; border-radius:8px; overflow:hidden;">
          <thead>
            <tr style="background:#fffff0;">
              <th style="padding:8px 12px; text-align:left; font-size:13px; color:#b7791f;">Ogłoszenie</th>
              <th style="padding:8px 12px; text-align:left; font-size:13px; color:#b7791f;">Co zrobić</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    ok_note = f'<p style="color:#276749; font-size:14px;">🟢 {len(ok)} ogłoszeń wygląda dobrze — nie wymagają działania.</p>' if ok else ""

    subject_emoji = "🚨" if urgent else ("⚠️" if medium else "✅")

    return f"""
<!DOCTYPE html>
<html lang="pl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f7fafc; font-family:Arial, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f7fafc; padding:24px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#ffffff; border-radius:12px; overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                     padding:28px 32px; color:#ffffff;">
            <h1 style="margin:0; font-size:24px;">👗 Vinted Tracker</h1>
            <p style="margin:6px 0 0; opacity:0.85; font-size:14px;">
              Raport z {now} &nbsp;·&nbsp; Cześć, <strong>{login}</strong>!
            </p>
          </td>
        </tr>

        <!-- Stats bar -->
        <tr>
          <td style="padding:20px 32px; background:#f8f9fa; border-bottom:1px solid #edf2f7;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="padding:0 8px;">
                  <div style="font-size:28px; font-weight:700; color:#2d3748;">
                    {stats.get('lacznie_ogloszen', 0)}
                  </div>
                  <div style="font-size:12px; color:#718096;">ogłoszeń</div>
                </td>
                <td align="center" style="padding:0 8px; border-left:1px solid #e2e8f0;">
                  <div style="font-size:28px; font-weight:700; color:#c53030;">
                    {stats.get('wymagaja_uwagi', 0)}
                  </div>
                  <div style="font-size:12px; color:#718096;">wymaga uwagi</div>
                </td>
                <td align="center" style="padding:0 8px; border-left:1px solid #e2e8f0;">
                  <div style="font-size:28px; font-weight:700; color:#2d3748;">
                    {stats.get('lacznie_wartosc', 0):.0f} zł
                  </div>
                  <div style="font-size:12px; color:#718096;">łączna wartość</div>
                </td>
                <td align="center" style="padding:0 8px; border-left:1px solid #e2e8f0;">
                  <div style="font-size:28px; font-weight:700; color:#2d3748;">
                    {stats.get('sredni_czas_na_rynku', 0):.0f} dni
                  </div>
                  <div style="font-size:12px; color:#718096;">śr. czas na rynku</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:24px 32px;">
            {urgent_section}
            {medium_section}
            {ok_note}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px; background:#f8f9fa; border-top:1px solid #edf2f7;
                     font-size:12px; color:#a0aec0; text-align:center;">
            Wygenerowano automatycznie przez Vinted Tracker &nbsp;·&nbsp;
            Aby zatrzymać raporty, zamknij scheduler.py
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_subject(stats: dict) -> str:
    urgent = stats.get("wymagaja_uwagi", 0)
    total  = stats.get("lacznie_ogloszen", 0)
    if urgent:
        return f"🚨 Vinted Tracker — {urgent} ogłoszeń wymaga działania ({total} łącznie)"
    return f"✅ Vinted Tracker — wszystko w porządku ({total} ogłoszeń)"


# ------------------------------------------------------------------ #
# Send
# ------------------------------------------------------------------ #

def send_email(config: dict, items: list[dict], stats: dict, login: str = "") -> None:
    """
    config keys required: email_to, email_from, email_password
    Optional: email_smtp_host (default smtp.gmail.com), email_smtp_port (default 587)
    """
    to_addr   = config["email_to"]
    from_addr = config["email_from"]
    password  = config["email_password"]
    smtp_host = config.get("email_smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("email_smtp_port", 587))

    html_body = build_html(items, stats, login)
    subject   = build_subject(stats)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Vinted Tracker <{from_addr}>"
    msg["To"]      = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(from_addr, password)
        server.sendmail(from_addr, to_addr, msg.as_string())
