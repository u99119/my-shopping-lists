"""CLI command handlers. Kept thin: argument parsing lives in cli.py."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from . import auth, calendar_client as cc, config as cfgmod, timing


def cmd_auth(args) -> int:
    cfg = cfgmod.load()
    path = args.client_secret or cfg.client_secret_path
    if not path:
        print("No client_secret path configured. Pass --client-secret <path> or run "
              "'gcal-push config set-client-secret <path>'.", file=sys.stderr)
        return 2
    creds = auth.run_oauth_flow(path)
    cfg.client_secret_path = path
    if args.email:
        cfg.account_email = args.email
    cfgmod.save(cfg)
    print("Authenticated. Token stored in OS keyring.")
    if creds.expiry:
        print(f"Access token expires at: {creds.expiry.isoformat()}Z (auto-refreshed)")
    return 0


def cmd_test(args) -> int:
    cfg = cfgmod.load()
    if not cfg.calendar_id:
        print("calendar_id not set. Run: gcal-push config set-calendar <id>", file=sys.stderr)
        return 2
    creds = auth.ensure_credentials(cfg.client_secret_path)
    now = datetime.now().astimezone()
    start = timing.push_now(now, buffer_minutes=1)
    ev = cc.create_event(creds, cfg.calendar_id, "MY CAL test — safe to ignore", start,
                         duration_min=0, popup_offset_min=cfg.popup_offset_min)
    print(f"Created test event {ev['id']} at {start.isoformat()} — deleting...")
    cc.delete_event(creds, cfg.calendar_id, ev["id"])
    print("Deleted. Sharing + auth OK.")
    return 0


def _resolve_time(args, now: datetime, phrase: Optional[cfgmod.Phrase]) -> datetime:
    if args.now:
        return timing.push_now(now)
    if args.at:
        hh, mm = timing.parse_hhmm(args.at)
        return timing.fixed_time(now, hh, mm)
    if args.next_half:
        return timing.next_half(now)
    if args.next_oclock:
        return timing.next_oclock(now)
    if args.in_hours is not None:
        return timing.x_hours_from_now(now, args.in_hours)
    if args.default:
        if not phrase:
            raise SystemExit("--default requires --phrase <index> (to read its default HH:MM).")
        return timing.default_time(now, phrase.default_hh, phrase.default_mm)
    raise SystemExit("Pick one time option: --now | --default | --at HH:MM | --next-half | "
                     "--next-oclock | --in-hours N")


def cmd_push(args) -> int:
    cfg = cfgmod.load()
    if not cfg.calendar_id:
        print("calendar_id not set. Run: gcal-push config set-calendar <id>", file=sys.stderr)
        return 2
    phrase: Optional[cfgmod.Phrase] = None
    if args.phrase is not None:
        if not (0 <= args.phrase < len(cfg.phrases)):
            print(f"Phrase index {args.phrase} out of range.", file=sys.stderr)
            return 2
        phrase = cfg.phrases[args.phrase]
        text = phrase.text
    elif args.text:
        text = args.text
    else:
        print("Pass --phrase <index> or --text <string>.", file=sys.stderr)
        return 2
    now = datetime.now().astimezone()
    start = _resolve_time(args, now, phrase)
    duration = phrase.duration_min if phrase else cfgmod.DEFAULT_DURATION_MIN
    if args.in_hours is not None:
        cfg.last_x_hours = args.in_hours
        cfgmod.save(cfg)
    creds = auth.ensure_credentials(cfg.client_secret_path)
    ev = cc.create_event(creds, cfg.calendar_id, text, start,
                         duration_min=duration, popup_offset_min=cfg.popup_offset_min)
    print(f"Pushed: '{text}' at {start.strftime('%a %Y-%m-%d %H:%M %Z')}  (id: {ev['id']})")
    return 0


def cmd_today(args) -> int:
    cfg = cfgmod.load()
    if not cfg.calendar_id:
        print("calendar_id not set.", file=sys.stderr)
        return 2
    creds = auth.ensure_credentials(cfg.client_secret_path)
    items = cc.list_today(creds, cfg.calendar_id, datetime.now().astimezone())
    if not items:
        print("(no events today)")
        return 0
    for ev in items:
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        print(f"  {start}  {ev.get('summary', '(no title)')}")
    return 0


def cmd_config(args) -> int:
    cfg = cfgmod.load()
    if args.action == "show":
        print(cfg.to_json())
        print(f"\n(config file: {cfgmod.config_path()})")
        return 0
    if args.action == "set-calendar":
        cfg.calendar_id = args.value
    elif args.action == "set-client-secret":
        cfg.client_secret_path = args.value
    elif args.action == "add-phrase":
        hh, mm = timing.parse_hhmm(args.at or "09:00")
        p = cfgmod.add_phrase(cfg, args.value, hh, mm)
        print(f"Added phrase #{len(cfg.phrases) - 1}: '{p.text}' @ {timing.format_hhmm(hh, mm)}")
    elif args.action == "remove-phrase":
        p = cfgmod.remove_phrase(cfg, int(args.value))
        print(f"Removed: '{p.text}'")
    elif args.action == "list-phrases":
        if not cfg.phrases:
            print("(no phrases)")
        for i, p in enumerate(cfg.phrases):
            print(f"  [{i:02d}] {p.text}  (default {timing.format_hhmm(p.default_hh, p.default_mm)})")
        return 0
    else:
        print(f"Unknown action: {args.action}", file=sys.stderr)
        return 2
    cfgmod.save(cfg)
    return 0


def cmd_logout(args) -> int:
    auth.clear_credentials()
    print("Cleared stored OAuth token.")
    return 0
