"""Install / remove the cron job for src/collect_daily.py (macOS / Linux).

The job tries every hour from 09:15 to 23:15; collect_daily.py skips once today's pull exists,
so a Mac that was asleep at 09:15 still collects later in the day.

    python3 scripts/install_daily_cron.py              # install
    python3 scripts/install_daily_cron.py --uninstall  # remove (after Fri 16 Oct)
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "# madt7202 daily collection"


def job():
    log = ROOT / "logs" / "daily.log"
    return f'15 9-23 * * * cd "{ROOT}" && "{sys.executable}" src/collect_daily.py >> "{log}" 2>&1'


def current():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else ""


def without_ours(text):
    out, skip = [], False
    for line in text.splitlines():
        if skip:
            skip = False
            continue
        if line.strip() == MARKER:
            skip = True
            continue
        out.append(line)
    return [x for x in out if x.strip()]


def write(lines):
    subprocess.run(["crontab", "-"], input="\n".join(lines) + ("\n" if lines else ""), text=True, check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--uninstall", action="store_true")
    a = p.parse_args()
    lines = without_ours(current())
    if a.uninstall:
        write(lines)
        print("removed madt7202 daily job")
        return
    (ROOT / "logs").mkdir(exist_ok=True)
    write(lines + [MARKER, job()])
    print("installed: tries hourly 09:15-23:15, one pull per day")
    print(job())


if __name__ == "__main__":
    main()
