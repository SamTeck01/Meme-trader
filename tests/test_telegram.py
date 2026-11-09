from bot.telegram import Telegram, parse_command


def test_parse():
    assert parse_command("/watch BONK") == ("watch", "BONK")
    assert parse_command("/status@MyBot") == ("status", "")
    assert parse_command("/rm -rf") is None and parse_command("hi") is None


def test_only_owner_obeyed():
    t = Telegram(token="x", chat_id="42")
    t.handle_update({"update_id": 1, "message": {"chat": {"id": 99}, "text": "/stop"}})
    assert t.pending() == []
    t.handle_update({"update_id": 2, "message": {"chat": {"id": 42}, "text": "/stop"}})
    assert t.pending() == [("stop", "")]
