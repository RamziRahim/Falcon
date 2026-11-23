"""Email for the daily paper job. Reads ~/.falcon/mail.env (written by setup_mail.sh, mode 600):
FALCON_MAIL_HOST, FALCON_MAIL_USER, FALCON_MAIL_PASS, FALCON_MAIL_TO.

    send_mail.py ok   <today> <log> <engine ok|notyet> <data last session>
    send_mail.py fail <today> <log> <what failed>
    send_mail.py test
"""
import glob
import os
import smtplib
import sys
from email.message import EmailMessage

CFG = os.path.expanduser("~/.falcon/mail.env")


def cfg():
    d = {}
    for line in open(CFG, encoding="utf-8"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            d[k] = v
    return d


def send(subject, body):
    c = cfg()
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, c["FALCON_MAIL_USER"], c["FALCON_MAIL_TO"]
    m.set_content(body)
    with smtplib.SMTP_SSL(c.get("FALCON_MAIL_HOST", "smtp.gmail.com"), 465, timeout=30) as s:
        s.login(c["FALCON_MAIL_USER"], c["FALCON_MAIL_PASS"])
        s.send_message(m)


def tail(path, n=40):
    try:
        return "".join(open(path, encoding="utf-8", errors="replace").readlines()[-n:])
    except OSError:
        return "(no log)"


def main():
    kind = sys.argv[1]
    if kind == "test":
        send("Falcon paper: test email from the Oracle server", "If you can read this, daily alerts will reach you.")
        print("sent")
        return
    today, log = sys.argv[2], sys.argv[3]
    if kind == "fail":
        send(f"Falcon paper FAILED {today}: {sys.argv[4]}",
             f"The daily paper job stopped at: {sys.argv[4]}\nThe 21:30 retry will run automatically.\n\nLast log lines:\n\n{tail(log)}")
        return
    engine, last = sys.argv[4], sys.argv[5]
    if engine == "notyet":
        send(f"Falcon paper {today}: data updated to {last} (paper trading starts 1 Dec)",
             f"NSE data updated to {last}. The engine starts after the 30 Nov 2026 close, per the frozen plan.\n\n{tail(log, 12)}")
        return
    rep = sorted(glob.glob("paper/reports/*.md"))
    orders = sorted(glob.glob("paper/orders/*.csv"))
    body = open(rep[-1], encoding="utf-8").read() if rep else "(no report)"
    newest = [o for o in orders if os.path.basename(o)[:10] >= last]
    for o in newest:
        body += f"\n\n--- ORDERS {os.path.basename(o)} ---\n" + open(o, encoding="utf-8").read()
    send(f"Falcon paper {last}" + (" - ORDERS for the next open" if newest else ""), body)


if __name__ == "__main__":
    main()
