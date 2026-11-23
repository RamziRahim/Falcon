#!/bin/bash
# Falcon paper trading, daily job on the Oracle server (cron, weekdays 19:30 and 21:30 IST).
# Updates NSE data, runs the frozen engine, saves records to branch paper-records, emails IA.
set -u
cd ~/falcon || exit 1
export PYTHONHASHSEED=0
TODAY=$(date +%F)
LOG=~/logs/daily_$TODAY.log
mkdir -p ~/logs
[ -f ~/logs/ok_$TODAY ] && exit 0                     # the 21:30 retry does nothing if 19:30 worked
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date) ==="
fail() { echo "FAILED: $1"; ~/venv/bin/python paper/server/send_mail.py fail "$TODAY" "$LOG" "$1"; exit 1; }
git fetch -q origin claude/swing-low-risk && git merge -q --ff-only origin/claude/swing-low-risk || fail "git update"
echo "code $(git rev-parse --short HEAD)"
~/venv/bin/python paper/data_update.py || fail "data update"
LAST=$(cat data/pit_v2/update_done.txt)
echo "data last session $LAST"
if ~/venv/bin/python paper/engine.py > ~/logs/engine_$TODAY.txt 2>&1; then
  ENGINE=ok
else
  if grep -q "before the first ranking day" ~/logs/engine_$TODAY.txt; then ENGINE=notyet; else cat ~/logs/engine_$TODAY.txt; fail "engine"; fi
fi
echo "engine $ENGINE"
if [ "$ENGINE" = ok ]; then
  R=~/records
  [ -d $R ] || git clone -q --single-branch --depth 1 -b paper-records git@github.com:RamziRahim/falcon.git $R
  (cd $R && git fetch -q origin paper-records && git reset -q --hard origin/paper-records)
  rm -rf $R/paper && mkdir -p $R/paper && cp -r paper/ledger paper/orders paper/reports paper/state.json $R/paper/ 2>/dev/null
  (cd $R && git add -A paper && git -c user.name=falcon-paper -c user.email=falcon-paper@localhost \
     commit -qm "Paper records $LAST (code $(cd ~/falcon && git rev-parse --short HEAD))" && git push -q origin HEAD:paper-records) \
     || echo "records: nothing new or push failed"
fi
~/venv/bin/python paper/server/send_mail.py ok "$TODAY" "$LOG" "$ENGINE" "$LAST" || echo "mail failed"
[ -n "${FALCON_PING:-}" ] && curl -fsS -m 10 "$FALCON_PING" > /dev/null
touch ~/logs/ok_$TODAY
echo "=== done $(date) ==="
