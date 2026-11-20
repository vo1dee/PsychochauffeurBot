"""Tests for TikTok/X photo-post support."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules import social_images
from modules.social_images import ImagePost, MediaItem, PostAudio
from modules.video_downloader import VideoDownloader


TIKWM_PHOTO = {
    "code": 0,
    "msg": "success",
    "data": {
        "title": "my slideshow",
        "play": "https://cdn.example/sound.mp3",
        "music": "https://cdn.example/sound.mp3",
        "music_info": {"title": "original sound", "author": "someone"},
        "images": ["https://cdn.example/1.jpeg", "https://cdn.example/2.jpeg"],
    },
}
TIKWM_VIDEO = {
    "code": 0,
    "data": {"title": "a video", "play": "https://cdn.example/v.mp4"},
}


class TestParsers:
    def test_tikwm_photo_post(self):
        post = social_images.parse_tikwm_images(TIKWM_PHOTO)
        assert post is not None
        assert post.platform == "tiktok"
        assert post.image_urls == TIKWM_PHOTO["data"]["images"]
        assert post.title == "my slideshow"
        assert post.audio == PostAudio(
            url="https://cdn.example/sound.mp3",
            title="original sound",
            performer="someone",
        )

    def test_tikwm_video_is_not_photo_post(self):
        assert social_images.parse_tikwm_images(TIKWM_VIDEO) is None
        assert social_images.parse_tikwm_images({"code": -1, "msg": "limit"}) is None

    def test_fxtwitter_photos(self):
        data = {
            "code": 200,
            "tweet": {
                "text": "look",
                "media": {
                    "photos": [
                        {"type": "photo", "url": "https://pbs.twimg.com/media/AAA.jpg"},
                        {"type": "photo", "url": "https://pbs.twimg.com/media/BBB.png?name=orig"},
                    ]
                },
            },
        }
        post = social_images.parse_fxtwitter(data)
        assert post is not None
        assert post.image_urls == [
            "https://pbs.twimg.com/media/AAA.jpg?name=large",
            "https://pbs.twimg.com/media/BBB.png?name=large",
        ]
        assert post.title == "look"

    def test_fxtwitter_mixed_tweet_keeps_all_media_in_order(self):
        data = {
            "code": 200,
            "tweet": {
                "media": {
                    "all": [
                        {"type": "video", "url": "https://video.twimg.com/v.mp4"},
                        {"type": "photo", "url": "https://pbs.twimg.com/media/AAA.jpg"},
                        {"type": "gif", "url": "https://video.twimg.com/g.mp4"},
                    ],
                }
            },
        }
        post = social_images.parse_fxtwitter(data)
        assert post is not None
        assert [(m.kind, m.url) for m in post.media] == [
            ("video", "https://video.twimg.com/v.mp4"),
            ("photo", "https://pbs.twimg.com/media/AAA.jpg?name=large"),
            ("video", "https://video.twimg.com/g.mp4"),
        ]

    def test_fxtwitter_video_only_tweet_stays_on_video_path(self):
        data = {
            "code": 200,
            "tweet": {
                "media": {
                    "all": [{"type": "video", "url": "https://video.twimg.com/x.mp4"}],
                    "videos": [{"type": "video", "url": "https://video.twimg.com/x.mp4"}],
                }
            },
        }
        assert social_images.parse_fxtwitter(data) is None
        assert social_images.parse_fxtwitter({"code": 200, "tweet": {"text": "hi"}}) is None

    def test_vxtwitter(self):
        data = {
            "text": "pics",
            "media_extended": [
                {"type": "image", "url": "https://pbs.twimg.com/media/CCC.jpg"}
            ],
        }
        post = social_images.parse_vxtwitter(data)
        assert post and post.image_urls == ["https://pbs.twimg.com/media/CCC.jpg?name=large"]
        data["media_extended"].append({"type": "video", "url": "https://v"})
        mixed = social_images.parse_vxtwitter(data)
        assert mixed and [m.kind for m in mixed.media] == ["photo", "video"]
        data["media_extended"].pop(0)
        assert social_images.parse_vxtwitter(data) is None

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://x.com/mannymarotta/status/2123771928464805991?s=46", "2123771928464805991"),
            ("https://fixupx.com/u/status/123/ua", "123"),
            ("https://d.fixupx.com/u/status/456", "456"),
            ("https://twitter.com/u/statuses/789", "789"),
        ],
    )
    def test_x_urls(self, url, expected):
        assert social_images.is_x_url(url)
        assert social_images.extract_x_status_id(url) == expected

    def test_non_x_urls(self):
        assert not social_images.is_x_url("https://x.com/user")
        assert not social_images.is_x_url("https://notx.com/u/status/1")

    def test_normalize_image_converts_webp(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (4, 4), "red").save(buf, format="WEBP")
        data, ext = social_images._normalize_image(buf.getvalue())
        assert ext == "jpg" and data[:3] == b"\xff\xd8\xff"

    def test_normalize_image_shrinks_large_photos(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (4000, 3000), "blue").save(buf, format="PNG")
        data, ext = social_images._normalize_image(buf.getvalue())
        assert ext == "jpg"
        with Image.open(BytesIO(data)) as img:
            assert max(img.size) == 2560

    def test_normalize_image_keeps_small_jpeg(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (800, 600), "green").save(buf, format="JPEG")
        raw = buf.getvalue()
        assert social_images._normalize_image(raw) == (raw, "jpg")


@pytest.fixture
def downloader(tmp_path):
    with patch.object(VideoDownloader, "_verify_yt_dlp"):
        vd = VideoDownloader(download_path=str(tmp_path), extract_urls_func=lambda t: [])
    return vd


def _make_items(tmp_path, kinds):
    items = []
    for i, kind in enumerate(kinds):
        p = tmp_path / f"m{i}.{'mp4' if kind == 'video' else 'jpg'}"
        p.write_bytes(b"\xff\xd8\xff" + b"0" * 10)
        items.append(MediaItem(kind, f"https://cdn/{i}", path=str(p)))
    return items


class TestVideoDownloaderPhotoPosts:
    @pytest.mark.asyncio
    async def test_fetch_image_post_tiktok(self, downloader, tmp_path):
        async def fake_download(items, *args, **kwargs):
            for i, item in enumerate(items):
                item.path = str(tmp_path / f"{i}.jpg")

        with patch.object(
            downloader, "_fetch_tikwm_data", AsyncMock(return_value=TIKWM_PHOTO)
        ), patch.object(social_images, "download_media", side_effect=fake_download):
            post = await downloader.fetch_image_post("https://vt.tiktok.com/ZSpErXFbh/")
        assert post is not None and len(post.paths) == 2 and post.audio

    @pytest.mark.asyncio
    async def test_fetch_image_post_tiktok_video_returns_none(self, downloader):
        with patch.object(
            downloader, "_fetch_tikwm_data", AsyncMock(return_value=TIKWM_VIDEO)
        ):
            assert await downloader.fetch_image_post("https://vt.tiktok.com/abc/") is None

    @pytest.mark.asyncio
    async def test_tikwm_fallback_skips_photo_posts(self, downloader):
        with patch.object(
            downloader, "_fetch_tikwm_data", AsyncMock(return_value=TIKWM_PHOTO)
        ), patch.object(social_images, "download_file", AsyncMock()) as dl:
            assert await downloader._download_tiktok_tikwm("https://vt.tiktok.com/a/") == (None, None)
        dl.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_album_with_sound_button(self, downloader, tmp_path):
        post = ImagePost(
            platform="tiktok",
            media=_make_items(tmp_path, ["photo"] * 12),
            audio=PostAudio(url="https://cdn/s.mp3", title="t", performer="p"),
        )
        bot = MagicMock()
        bot.send_media_group = AsyncMock(return_value=[SimpleNamespace(message_id=77)])
        bot.send_message = AsyncMock()
        ok = await downloader.send_image_post(
            bot, 1, post, "cap", source_url="https://vt.tiktok.com/x/"
        )
        assert ok == "sent"
        assert bot.send_media_group.await_count == 2  # 10 + 2
        first_media = bot.send_media_group.await_args_list[0].kwargs["media"]
        assert len(first_media) == 10 and first_media[0].caption == "cap"
        assert first_media[1].caption is None
        msg_kwargs = bot.send_message.await_args.kwargs
        assert msg_kwargs["reply_to_message_id"] == 77
        callback = msg_kwargs["reply_markup"].inline_keyboard[0][0].callback_data
        assert callback.startswith("ttaudio:")
        assert callback.split(":")[1] in downloader._post_audio_requests

    @pytest.mark.asyncio
    async def test_send_single_photo_attaches_button(self, downloader, tmp_path):
        post = ImagePost(
            platform="tiktok",
            media=_make_items(tmp_path, ["photo"]),
            audio=PostAudio(url="https://cdn/s.mp3"),
        )
        bot = MagicMock()
        bot.send_photo = AsyncMock()
        bot.send_message = AsyncMock()
        assert await downloader.send_image_post(bot, 1, post, "cap", source_url="u")
        assert bot.send_photo.await_args.kwargs["reply_markup"] is not None
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_timeout_is_reported_not_raised(self, downloader, tmp_path):
        from telegram.error import TimedOut

        post = ImagePost(platform="x", media=_make_items(tmp_path, ["photo"] * 12))
        bot = MagicMock()
        bot.send_media_group = AsyncMock(
            side_effect=[TimedOut(), [SimpleNamespace(message_id=2)]]
        )
        assert await downloader.send_image_post(bot, 1, post, "cap") == "timed_out"
        assert bot.send_media_group.await_count == 2  # later parts still sent

    @pytest.mark.asyncio
    async def test_timeout_keeps_link_and_skips_video_fallback(self, downloader, tmp_path):
        post = ImagePost(platform="tiktok", media=_make_items(tmp_path, ["photo"]))
        message = MagicMock(reply_to_message=None)
        message.delete = AsyncMock()
        update = SimpleNamespace(
            message=message,
            effective_chat=SimpleNamespace(id=1, type="private"),
            effective_user=SimpleNamespace(id=2, username="u", first_name="u"),
        )
        context = SimpleNamespace(bot=MagicMock())
        context.bot.send_chat_action = AsyncMock()
        with patch.object(
            downloader, "fetch_image_post", AsyncMock(return_value=post)
        ), patch.object(
            downloader, "send_image_post", AsyncMock(return_value="timed_out")
        ):
            handled = await downloader._try_send_image_post(update, context, "https://vt.tiktok.com/x/")
        assert handled is True
        message.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_mixed_x_album(self, downloader, tmp_path):
        from telegram import InputMediaPhoto, InputMediaVideo

        items = _make_items(tmp_path, ["photo", "video", "photo"])
        items.append(MediaItem("video", "https://cdn/failed"))  # download failed
        post = ImagePost(platform="x", media=items)
        bot = MagicMock()
        bot.send_media_group = AsyncMock(return_value=[SimpleNamespace(message_id=1)])
        bot.send_message = AsyncMock()
        assert await downloader.send_image_post(bot, 1, post, "cap", source_url="u")
        media = bot.send_media_group.await_args.kwargs["media"]
        assert [type(m) for m in media] == [InputMediaPhoto, InputMediaVideo, InputMediaPhoto]
        bot.send_message.assert_not_called()  # no sound button for X

    @pytest.mark.asyncio
    async def test_send_single_remaining_video(self, downloader, tmp_path):
        post = ImagePost(
            platform="x",
            media=[MediaItem("photo", "https://cdn/x")] + _make_items(tmp_path, ["video"]),
        )
        bot = MagicMock()
        bot.send_video = AsyncMock()
        assert await downloader.send_image_post(bot, 1, post, "cap")
        assert "video" in bot.send_video.await_args.kwargs

    @pytest.mark.asyncio
    async def test_audio_callback_sends_audio_and_removes_button_message(
        self, downloader
    ):
        downloader._post_audio_requests["abcd1234"] = {
            "url": "https://cdn/s.mp3",
            "title": "t",
            "performer": "p",
            "source_url": "https://vt.tiktok.com/x/",
        }
        message = MagicMock(
            chat_id=5,
            message_id=10,
            photo=None,
            reply_to_message=SimpleNamespace(message_id=9),
        )
        message.delete = AsyncMock()
        update = SimpleNamespace(
            callback_query=SimpleNamespace(data="ttaudio:abcd1234", message=message)
        )
        context = SimpleNamespace(bot=MagicMock())
        context.bot.send_audio = AsyncMock()

        async def fake_download(url, path, timeout=60):
            with open(path, "wb") as f:
                f.write(b"ID3")
            return True

        with patch.object(social_images, "download_file", side_effect=fake_download):
            await downloader.handle_post_audio_callback(update, context)

        kwargs = context.bot.send_audio.await_args.kwargs
        assert kwargs["reply_to_message_id"] == 9
        assert kwargs["title"] == "t" and kwargs["performer"] == "p"
        message.delete.assert_awaited_once()
        assert not [f for f in os.listdir(downloader.download_path) if f.endswith(".mp3")]
