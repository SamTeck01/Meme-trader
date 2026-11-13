"""Telegram bot (STRATEGY.md §8): alerts + owner commands, via long polling (no webhook).

Only messages from TELEGRAM_CHAT_ID are obeyed. Commands are queued and executed by the
main loop, so the trading state is only ever touched from one thread.
"""
import os
import queue
import threading

import httpx

API = "https://api.telegram.org/bot{t}/{m}"
COMMANDS = {"status", "stop", "start", "watch", "unwatch", "positions", "pnl", "report", "help"}
HELP = ("/status /positions /pnl\n/report — which signals are actually making money\n/watch <ticker|CA>  /unwatch <ticker|CA>\n"
        "/stop — sell all and halt   /start — resume")


def parse_command(text: str) -> tuple[str, str] | None:
    if not text or not text.startswith("/"):
        return None
    head, _, arg = text.strip().partition(" ")
    cmd = head[1:].split("@")[0].lower()
    return (cmd, arg.strip()) if cmd in COMMANDS else None


class Telegram:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id or os.getenv("TELEGRAM_CHAT_ID", ""))
        self.commands: queue.Queue[tuple[str, str]] = queue.Queue()
        self._offset = 0

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _call(self, method: str, timeout: float = 15, **params):
        r = httpx.post(API.format(t=self.token, m=method), json=params, timeout=timeout)
        r.raise_for_status()
        return r.json().get("result")

    def send(self, text: str) -> None:
        if not (self.enabled and self.chat_id):
            return
        try:
            self._call("sendMessage", chat_id=self.chat_id, text=text[:4000], disable_web_page_preview=True)
        except httpx.HTTPError:
            pass   # alerts are best-effort; never crash trading over Telegram

    def handle_update(self, u: dict) -> None:
        self._offset = max(self._offset, u.get("update_id", 0) + 1)
        msg = u.get("message") or {}
        chat = str((msg.get("chat") or {}).get("id", ""))
        if not self.chat_id:
            # first-run helper: tell the user their chat id, obey nothing
            if chat:
                try:
                    self._call("sendMessage", chat_id=chat,
                               text=f"Set TELEGRAM_CHAT_ID={chat} on the server to control this bot.")
                except httpx.HTTPError:
                    pass
            return
        if chat != self.chat_id:
            return
        cmd = parse_command(msg.get("text", ""))
        if cmd:
            self.commands.put(cmd)

    def _loop(self) -> None:
        while True:
            try:
                for u in self._call("getUpdates", 40, offset=self._offset, timeout=30) or []:
                    self.handle_update(u)
            except Exception:
                threading.Event().wait(5)

    def start(self) -> None:
        if self.enabled:
            threading.Thread(target=self._loop, daemon=True).start()

    def pending(self) -> list[tuple[str, str]]:
        out = []
        while not self.commands.empty():
            out.append(self.commands.get_nowait())
        return out
