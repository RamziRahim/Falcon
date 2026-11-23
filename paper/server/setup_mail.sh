#!/bin/bash
# IA runs this once on the server and types the details; nothing is echoed or stored elsewhere.
mkdir -p ~/.falcon && chmod 700 ~/.falcon
read -p "Email address that sends the alerts (your Gmail): " U
read -s -p "Its app password (typing is hidden): " P; echo
read -p "Send alerts to (press Enter for the same address): " T
[ -z "$T" ] && T="$U"
umask 077
printf 'FALCON_MAIL_HOST=smtp.gmail.com\nFALCON_MAIL_USER=%s\nFALCON_MAIL_PASS=%s\nFALCON_MAIL_TO=%s\n' "$U" "${P// /}" "$T" > ~/.falcon/mail.env
chmod 600 ~/.falcon/mail.env
cd ~/falcon && ~/venv/bin/python paper/server/send_mail.py test && echo "Test email sent - check your inbox."
