"""Tests for modules.recap: header formatting, splitting, generation and the tick job."""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from modules import recap


class TestFormatRecapHeader:
    def test_single_day(self) -> None:
        header = recap.format_recap_header("Гурт", date(2026, 9, 27))
        assert header == "📜 <b>РЕКАП Гурт | 27 вересня</b>"

    def test_first_day_of_month(self) -> None:
        header = recap.format_recap_header("Гурт", date(2026, 10, 1))
        assert header == "📜 <b>РЕКАП Гурт | 1 жовтня</b>"

    def test_no_title(self) -> None:
        header = recap.format_recap_header(None, date(2026, 9, 27))
        assert header == "📜 <b>РЕКАП | 27 вересня</b>"


class TestSplitRecap:
    def test_short_text_not_split(self) -> None:
        text = "short"
        assert recap._split_recap(text) == [text]

    def test_splits_on_section_boundary(self) -> None:
        # Two adjacent short sections should be combined into one chunk,
        # while a section that would overflow starts a new chunk.
        short_a, short_b, long_c = "a" * 500, "b" * 500, "c" * 3500
        text = "\n\n".join([short_a, short_b, long_c])
        chunks = recap._split_recap(text, max_len=4000)
        assert len(chunks) == 2
        assert chunks[0] == f"{short_a}\n\n{short_b}"
        assert chunks[1] == long_c
        for chunk in chunks:
            assert len(chunk) <= 4000

    def test_hard_splits_oversized_section(self) -> None:
        section = "y" * 9000
        chunks = recap._split_recap(section, max_len=4000)
        assert all(len(c) <= 4000 for c in chunks)
        assert "".join(chunks) == section


class TestBuildInputText:
    def test_username_preferred_over_first_name(self) -> None:
        rows = [(datetime(2026, 9, 26, 12, 0), "someuser", "Ім'я", "привіт")]
        text = recap._build_input_text(rows)
        assert text == "[12:00] @someuser: привіт"

    def test_falls_back_to_first_name(self) -> None:
        rows = [(datetime(2026, 9, 26, 12, 0), None, "Ім'я", "привіт")]
        text = recap._build_input_text(rows)
        assert text == "[12:00] Ім'я: привіт"

    def test_truncates_to_most_recent(self) -> None:
        rows = [
            (datetime(2026, 9, 26, h, 0), "u", None, "x" * 100)
            for h in range(10)
        ]
        with patch.object(recap, "RECAP_MAX_INPUT_CHARS", 250):
            text = recap._build_input_text(rows)
        # Only the most recent lines should survive, in chronological order.
        assert text.endswith("[09:00] @u: " + "x" * 100)
        assert "[00:00]" not in text


@pytest.mark.asyncio
class TestGenerateRecap:
    async def test_below_threshold_returns_none(self) -> None:
        with patch.object(recap, "get_messages_for_recap", new=AsyncMock(return_value=[
            (datetime(2026, 9, 26, 12, 0), "u", None, "hi")
        ])):
            result = await recap.generate_recap(123, date(2026, 9, 26), min_messages=5)
        assert result is None

    async def test_now_bypasses_threshold(self) -> None:
        rows = [(datetime(2026, 9, 26, 12, 0), "u", None, "hi")]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value={
            "choices": [{"message": {"content": "Тіло рекапу"}}]
        })
        mock_config_manager = MagicMock()
        mock_config_manager.get_config = AsyncMock(return_value={})
        with patch.object(recap, "get_messages_for_recap", new=AsyncMock(return_value=rows)), \
             patch.object(recap.Database, "get_chat_info", new=AsyncMock(return_value={"title": "Чат", "chat_type": "group"})), \
             patch.object(recap, "get_shared_config_manager", new=MagicMock(return_value=mock_config_manager)), \
             patch.object(recap, "get_system_prompt", new=AsyncMock(return_value="prompt")), \
             patch.object(recap, "client", new=mock_client):
            result = await recap.generate_recap(123, date(2026, 9, 26), min_messages=1)
        assert result is not None
        assert "Тіло рекапу" in result
        assert "РЕКАП" in result

    async def test_llm_failure_returns_none(self) -> None:
        rows = [(datetime(2026, 9, 26, 12, 0), "u", None, "hi")] * 25
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
        mock_config_manager = MagicMock()
        mock_config_manager.get_config = AsyncMock(return_value={})
        with patch.object(recap, "get_messages_for_recap", new=AsyncMock(return_value=rows)), \
             patch.object(recap.Database, "get_chat_info", new=AsyncMock(return_value=None)), \
             patch.object(recap, "get_shared_config_manager", new=MagicMock(return_value=mock_config_manager)), \
             patch.object(recap, "get_system_prompt", new=AsyncMock(return_value="prompt")), \
             patch.object(recap, "client", new=mock_client):
            result = await recap.generate_recap(123, date(2026, 9, 26))
        assert result is None


@pytest.mark.asyncio
class TestSendRecap:
    async def test_sends_html(self) -> None:
        bot = MagicMock()
        bot.send_message = AsyncMock()
        await recap.send_recap(bot, 1, "short text", pin=False)
        bot.send_message.assert_awaited_once()
        _, kwargs = bot.send_message.call_args
        assert kwargs.get("parse_mode") is not None

    async def test_falls_back_to_plain_text_on_bad_request(self) -> None:
        from telegram.error import BadRequest
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=[BadRequest("bad html"), None])
        await recap.send_recap(bot, 1, "<b>broken", pin=False)
        assert bot.send_message.await_count == 2
        second_call_args = bot.send_message.call_args_list[1]
        assert "<b>" not in second_call_args.args[1]

    async def test_pins_first_sent_message_by_default(self) -> None:
        bot = MagicMock()
        sent_message = MagicMock(message_id=555)
        bot.send_message = AsyncMock(return_value=sent_message)
        with patch.object(recap, "_pin_recap_message", new=AsyncMock()) as mock_pin:
            await recap.send_recap(bot, 1, "short text")
        mock_pin.assert_awaited_once_with(bot, 1, sent_message)

    async def test_pin_false_skips_pinning(self) -> None:
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=MagicMock(message_id=555))
        with patch.object(recap, "_pin_recap_message", new=AsyncMock()) as mock_pin:
            await recap.send_recap(bot, 1, "short text", pin=False)
        mock_pin.assert_not_called()

    async def test_no_pin_when_every_chunk_failed_to_send(self) -> None:
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=RuntimeError("network down"))
        with patch.object(recap, "_pin_recap_message", new=AsyncMock()) as mock_pin:
            await recap.send_recap(bot, 1, "short text")
        mock_pin.assert_not_called()


@pytest.mark.asyncio
class TestPinRecapMessage:
    async def test_pins_message_silently_and_records_it(self) -> None:
        bot = MagicMock()
        bot.pin_chat_message = AsyncMock()
        message = MagicMock(message_id=42)
        with patch.object(recap.Database, "set_recap_pinned_message", new=AsyncMock()) as mock_set:
            await recap._pin_recap_message(bot, 1, message)

        bot.pin_chat_message.assert_awaited_once_with(1, 42, disable_notification=True)
        mock_set.assert_awaited_once_with(1, 42)

    async def test_leaves_earlier_recap_pins_in_place(self) -> None:
        # Pinning a new recap must never unpin an earlier one — pins are meant
        # to accumulate into a browsable history in the chat.
        bot = MagicMock()
        bot.pin_chat_message = AsyncMock()
        bot.unpin_chat_message = AsyncMock()
        message = MagicMock(message_id=99)
        with patch.object(recap.Database, "set_recap_pinned_message", new=AsyncMock()):
            await recap._pin_recap_message(bot, 1, message)

        bot.unpin_chat_message.assert_not_called()

    async def test_pin_failure_is_swallowed(self) -> None:
        bot = MagicMock()
        bot.pin_chat_message = AsyncMock(side_effect=RuntimeError("bot lacks rights"))
        message = MagicMock(message_id=42)
        with patch.object(recap.Database, "set_recap_pinned_message", new=AsyncMock()):
            await recap._pin_recap_message(bot, 1, message)  # must not raise


@pytest.mark.asyncio
class TestRecapTick:
    async def test_skips_chat_already_sent_today(self) -> None:
        today = date(2026, 9, 27)
        rows = [{"chat_id": 1, "send_time": "09:00", "last_sent_date": today}]
        context = MagicMock()
        context.bot = MagicMock()

        with patch.object(recap.Database, "get_enabled_recap_chats", new=AsyncMock(return_value=rows)), \
             patch.object(recap, "datetime") as mock_dt, \
             patch.object(recap, "generate_recap", new=AsyncMock()) as mock_generate, \
             patch.object(recap.Database, "mark_recap_sent", new=AsyncMock()) as mock_mark:
            mock_dt.now.return_value = datetime(2026, 9, 27, 10, 0)
            await recap.recap_tick(context)

        mock_generate.assert_not_called()
        mock_mark.assert_not_called()

    async def test_skips_chat_before_send_time(self) -> None:
        rows = [{"chat_id": 1, "send_time": "09:30", "last_sent_date": None}]
        context = MagicMock()
        context.bot = MagicMock()

        with patch.object(recap.Database, "get_enabled_recap_chats", new=AsyncMock(return_value=rows)), \
             patch.object(recap, "datetime") as mock_dt, \
             patch.object(recap, "generate_recap", new=AsyncMock()) as mock_generate:
            mock_dt.now.return_value = datetime(2026, 9, 27, 9, 0)
            await recap.recap_tick(context)

        mock_generate.assert_not_called()

    async def test_sends_due_chat_and_marks_sent_first(self) -> None:
        rows = [{"chat_id": 1, "send_time": "09:00", "last_sent_date": None}]
        context = MagicMock()
        context.bot = MagicMock()
        call_order = []

        async def fake_mark(chat_id: int, sent_date: date) -> bool:
            call_order.append("mark")
            return True

        async def fake_generate(chat_id: int, target_date: date) -> str:
            call_order.append("generate")
            return "the recap"

        with patch.object(recap.Database, "get_enabled_recap_chats", new=AsyncMock(return_value=rows)), \
             patch.object(recap, "datetime") as mock_dt, \
             patch.object(recap.Database, "mark_recap_sent", new=fake_mark), \
             patch.object(recap, "generate_recap", new=fake_generate), \
             patch.object(recap, "send_recap", new=AsyncMock()) as mock_send:
            mock_dt.now.return_value = datetime(2026, 9, 27, 9, 30)
            await recap.recap_tick(context)

        assert call_order == ["mark", "generate"]
        mock_send.assert_awaited_once_with(context.bot, 1, "the recap")

    async def test_skips_when_claim_lost_to_another_process(self) -> None:
        # mark_recap_sent returning False means another process/tick already
        # claimed today for this chat (the WHERE clause matched no row).
        rows = [{"chat_id": 1, "send_time": "09:00", "last_sent_date": None}]
        context = MagicMock()
        context.bot = MagicMock()

        with patch.object(recap.Database, "get_enabled_recap_chats", new=AsyncMock(return_value=rows)), \
             patch.object(recap, "datetime") as mock_dt, \
             patch.object(recap.Database, "mark_recap_sent", new=AsyncMock(return_value=False)), \
             patch.object(recap, "generate_recap", new=AsyncMock()) as mock_generate, \
             patch.object(recap, "send_recap", new=AsyncMock()) as mock_send:
            mock_dt.now.return_value = datetime(2026, 9, 27, 9, 30)
            await recap.recap_tick(context)

        mock_generate.assert_not_called()
        mock_send.assert_not_called()
