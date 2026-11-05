"""CLI entry point:  python -m msl.cal.cli  (wrapper: bin/gcal-push)"""

from __future__ import annotations

import argparse
from typing import Optional

from . import commands


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gcal-push",
                                description="Push events to a shared Google Calendar.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("auth", help="Run OAuth flow and store token.")
    a.add_argument("--client-secret", help="Path to client_secret_*.json.")
    a.add_argument("--email", help="Record which Gmail you signed in as (display only).")
    a.set_defaults(func=commands.cmd_auth)

    t = sub.add_parser("test", help="Create + delete a dummy event to validate setup.")
    t.set_defaults(func=commands.cmd_test)

    pu = sub.add_parser("push", help="Push an event.")
    pu.add_argument("--phrase", type=int, help="Phrase index from 'config list-phrases'.")
    pu.add_argument("--text", help="Ad-hoc text (if not using a phrase).")
    pu.add_argument("--now", action="store_true", help="Push NOW (now + 5 min).")
    pu.add_argument("--default", action="store_true", help="Push at phrase's default HH:MM.")
    pu.add_argument("--at", help="Push at fixed HH:MM today (rolls to tomorrow if past).")
    pu.add_argument("--next-half", action="store_true", help="Push at strictly next :30.")
    pu.add_argument("--next-oclock", action="store_true", help="Push at strictly next :00.")
    pu.add_argument("--in-hours", type=int, help="Push at N-th upcoming hour mark.")
    pu.set_defaults(func=commands.cmd_push)

    tod = sub.add_parser("today", help="List today's events on the shared calendar.")
    tod.set_defaults(func=commands.cmd_today)

    cf = sub.add_parser("config", help="Read/update local config.")
    cf.add_argument("action", choices=["show", "set-calendar", "set-client-secret",
                                        "add-phrase", "remove-phrase", "list-phrases"])
    cf.add_argument("value", nargs="?", help="Value (ID, path, phrase text, or index).")
    cf.add_argument("--at", help="With add-phrase: default HH:MM (default 09:00).")
    cf.set_defaults(func=commands.cmd_config)

    lo = sub.add_parser("logout", help="Clear stored OAuth token.")
    lo.set_defaults(func=commands.cmd_logout)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
