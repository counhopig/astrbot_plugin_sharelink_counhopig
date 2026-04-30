"""
YouTube 平台适配器。

使用 youtube-transcript-api 提取字幕（手动字幕 + 自动生成字幕），
yt-dlp 获取视频元信息，yt-dlp 下载音频作为后备方案。
"""

from __future__ import annotations

import re
import traceback
from typing import Optional
from urllib.parse import parse_qs, urlparse

from astrbot.api import logger

from .base import BasePlatformAdapter, VideoMetadata

# ─── YouTube 常量 ─────────────────────────────────────────────────────────────

YOUTUBE_URL_PATTERNS = [
    re.compile(r"youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/live/([a-zA-Z0-9_-]{11})"),
]

# 字幕语言优先级（中文优先，其次是英文）
SUBTITLE_LANGUAGE_PRIORITY = [
    "zh-Hans", "zh-CN", "zh-TW", "zh-Hant", "zh",
    "en", "en-US", "en-GB",
]

# Lazy import youtube_transcript_api
_youtube_transcript_api = None


def _get_youtube_transcript_api():
    global _youtube_transcript_api
    if _youtube_transcript_api is None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            _youtube_transcript_api = YouTubeTranscriptApi
        except ImportError:
            logger.error(
                "[YouTubeAdapter] youtube-transcript-api 未安装。"
                "请执行: pip install youtube-transcript-api"
            )
            raise
    return _youtube_transcript_api


# Lazy import yt_dlp for metadata extraction
_yt_dlp = None


def _get_yt_dlp():
    global _yt_dlp
    if _yt_dlp is None:
        import yt_dlp

        _yt_dlp = yt_dlp
    return _yt_dlp


class YouTubeAdapter(BasePlatformAdapter):
    """YouTube 视频适配器。"""

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def display_name(self) -> str:
        return "YouTube"

    # ── URL 匹配与解析 ────────────────────────────────────────────────────

    def match(self, url: str) -> bool:
        """判断 URL 是否为 YouTube 链接。"""
        for pattern in YOUTUBE_URL_PATTERNS:
            if pattern.search(url):
                return True
        # 纯视频 ID（11位）
        if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url):
            return True
        return False

    def extract_id(self, url: str) -> Optional[str]:
        """从 URL 或纯 ID 中提取 YouTube video ID。

        YouTube video ID 为 11 位字符串，如 "dQw4w9WgXcQ"。
        """
        # 先尝试 URL 匹配
        for pattern in YOUTUBE_URL_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)

        # 再尝试纯 ID
        if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url):
            return url

        return None

    # ── 数据获取 ──────────────────────────────────────────────────────────

    async def fetch_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """使用 yt-dlp 获取 YouTube 视频元信息。

        Args:
            video_id: YouTube video ID（11位字符串）。
        """
        try:
            yt_dlp = _get_yt_dlp()
        except ImportError:
            logger.error("[YouTubeAdapter] yt-dlp 未安装")
            return None

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            import asyncio

            loop = asyncio.get_running_loop()

            def _extract():
                ydl_opts = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(video_url, download=False)

            info = await loop.run_in_executor(None, _extract)

            if not info:
                return None

            return VideoMetadata(
                video_id=video_id,
                title=info.get("title", ""),
                platform=self.name,
                description=info.get("description", "")[:500],
                duration=int(info.get("duration", 0) or 0),
                owner=info.get("uploader", ""),
                thumbnail_url=info.get("thumbnail", ""),
            )

        except Exception as e:
            logger.error(
                f"[YouTubeAdapter] 获取视频信息失败: "
                f"{e}\n{traceback.format_exc()}"
            )
            return None

    async def fetch_subtitles(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """使用 youtube-transcript-api 获取 YouTube 字幕文本。

        优先获取手动字幕，其次获取自动生成字幕。

        Args:
            video_id: YouTube video ID。
            max_length: 最大字符数，超出截断。
        """
        try:
            YouTubeTranscriptApi = _get_youtube_transcript_api()
        except ImportError:
            return None

        try:
            # 获取可用字幕列表
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            transcript = None

            # 1. 尝试找手动字幕（按优先级）
            for lang in SUBTITLE_LANGUAGE_PRIORITY:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    if transcript and not transcript.is_generated:
                        break
                except Exception:
                    continue

            # 2. 如果没找到手动字幕，尝试自动生成字幕
            if transcript is None or transcript.is_generated:
                for lang in SUBTITLE_LANGUAGE_PRIORITY:
                    try:
                        generated = transcript_list.find_generated_transcript([lang])
                        if generated:
                            transcript = generated
                            break
                    except Exception:
                        continue

            # 3. 如果还是没找到，用第一个可用的（无论什么语言）
            if transcript is None:
                try:
                    available = list(transcript_list)
                    if available:
                        transcript = available[0]
                except Exception:
                    pass

            if transcript is None:
                logger.info(f"[YouTubeAdapter] 视频 {video_id} 无可用字幕")
                return None

            # 获取字幕内容
            fetched = transcript.fetch()

            if not fetched:
                return None

            # 拼接文本
            lines = [item.get("text", "").strip() for item in fetched]
            full_text = "\n".join(filter(None, lines))

            if not full_text:
                return None

            # 截断
            if len(full_text) > max_length:
                full_text = full_text[:max_length] + "\n...(字幕已截断)"
                logger.info(
                    f"[YouTubeAdapter] 字幕过长 → 已截断至 {max_length}"
                )

            logger.info(
                f"[YouTubeAdapter] 字幕获取成功: {video_id} "
                f"({transcript.language}, {len(full_text)} 字符)"
            )
            return full_text

        except Exception as e:
            # youtube-transcript-api 常见的异常：
            # - TranscriptsDisabled: 视频关闭了字幕
            # - NoTranscriptFound: 没有对应语言的字幕
            # - VideoUnavailable: 视频不可用
            logger.info(f"[YouTubeAdapter] 字幕获取失败 {video_id}: {e}")
            return None

    def get_video_url(self, video_id: str) -> str:
        """返回 YouTube 视频完整 URL（供 yt-dlp 使用）。"""
        return f"https://www.youtube.com/watch?v={video_id}"
