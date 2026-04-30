"""
Bilibili（B站）平台适配器。

使用 bilibili-api-python 获取视频信息与字幕，
同时保留 REST API 作为后备方案。
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import traceback
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from astrbot.api import logger

from .base import BasePlatformAdapter, VideoMetadata

# ─── B站常量 ─────────────────────────────────────────────────────────────────

BVID_PATTERN = re.compile(r"(?:bv|BV)([a-zA-Z0-9]{10})")
AVID_PATTERN = re.compile(r"(?:av|AV)(\d+)")

BILIBILI_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# ─── 懒加载 ───────────────────────────────────────────────────────────────────

_yt_dlp = None
_bilibili_api_available: bool | None = None


def _get_yt_dlp():
    global _yt_dlp
    if _yt_dlp is None:
        import yt_dlp

        _yt_dlp = yt_dlp
    return _yt_dlp


def _check_bilibili_api() -> bool:
    global _bilibili_api_available
    if _bilibili_api_available is None:
        try:
            import bilibili_api  # noqa: F401

            _bilibili_api_available = True
        except ImportError:
            _bilibili_api_available = False
    return _bilibili_api_available


class BilibiliAdapter(BasePlatformAdapter):
    """Bilibili（B站）视频适配器。"""

    def __init__(self, sessdata: str = "", bili_jct: str = "") -> None:
        self._sessdata = sessdata
        self._bili_jct = bili_jct
        self._use_api = _check_bilibili_api()
        if self._use_api:
            logger.info(
                "[BilibiliAdapter] bilibili-api-python 已加载，将使用官方库获取信息"
            )
        else:
            logger.info(
                "[BilibiliAdapter] bilibili-api-python 未安装，"
                "使用 REST API 回落"
            )

    @property
    def name(self) -> str:
        return "bilibili"

    @property
    def display_name(self) -> str:
        return "B站"

    # ── URL 匹配与解析 ────────────────────────────────────────────────────

    def match(self, url: str) -> bool:
        """判断 URL 是否为 B站链接或纯 BV/AV 号。"""
        if BVID_PATTERN.search(url) or AVID_PATTERN.search(url):
            return True
        try:
            parsed = urlparse(url)
            if "bilibili.com" in parsed.netloc or "b23.tv" in parsed.netloc:
                return True
        except Exception:
            pass
        return False

    def extract_id(self, url: str) -> Optional[str]:
        """从 URL 或纯 ID 中提取 BV 号（不含 BV 前缀）。"""
        match = BVID_PATTERN.search(url)
        if match:
            return match.group(1)
        return None

    async def resolve_url(self, url: str) -> Optional[str]:
        """解析 b23.tv 短链接，返回完整 B站视频 URL。"""
        if "b23.tv" not in url:
            return None

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers=BILIBILI_API_HEADERS,
            ) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    final_url = str(resp.url)
                    bv_match = BVID_PATTERN.search(final_url)
                    if bv_match:
                        return (
                            "https://www.bilibili.com/video/BV"
                            + bv_match.group(1)
                        )
                    logger.warning(
                        f"[BilibiliAdapter] b23.tv 解析返回: {final_url}"
                    )
                    return None
        except Exception as e:
            logger.error(f"[BilibiliAdapter] b23.tv 解析失败: {e}")
            return None

    # ── 数据获取 ──────────────────────────────────────────────────────────

    async def fetch_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """获取视频元信息。

        优先使用 bilibili-api-python（支持 Cookie 鉴权），
        失败时回落到 REST API。
        """
        if self._use_api:
            result = await self._fetch_metadata_via_api(video_id)
            if result:
                return result
            logger.info(
                "[BilibiliAdapter] bilibili-api 获取元信息失败，"
                "回落到 REST API"
            )

        return await self._fetch_metadata_via_rest(video_id)

    async def fetch_subtitles(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """获取视频字幕文本。

        优先使用 bilibili-api-python，失败时回落到 REST API。
        """
        if self._use_api:
            result = await self._fetch_subtitles_via_api(
                video_id, max_length
            )
            if result:
                return result
            logger.info(
                "[BilibiliAdapter] bilibili-api 获取字幕失败，"
                "回落到 REST API"
            )

        return await self._fetch_subtitles_via_rest(video_id, max_length)

    def get_video_url(self, video_id: str) -> str:
        """返回 B站视频完整 URL（供 yt-dlp 使用）。"""
        return f"https://www.bilibili.com/video/BV{video_id}"

    async def download_audio(
        self, video_id: str, timeout: int = 300
    ) -> Optional[str]:
        """使用 yt-dlp 下载视频音频作为字幕后备方案。"""
        try:
            yt_dlp = _get_yt_dlp()
        except ImportError:
            logger.error(
                "[BilibiliAdapter] yt-dlp 未安装，请执行: pip install yt-dlp"
            )
            return None

        video_url = self.get_video_url(video_id)
        temp_dir = tempfile.gettempdir()
        output_template = os.path.join(
            temp_dir, f"bilibili_audio_{video_id}.%(ext)s"
        )

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": output_template,
            "restrict_filenames": True,
            "http_headers": {
                "User-Agent": BILIBILI_API_HEADERS["User-Agent"],
                "Referer": "https://www.bilibili.com/",
            },
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
        }

        try:
            loop = asyncio.get_running_loop()

            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])

            await asyncio.wait_for(
                loop.run_in_executor(None, _download),
                timeout=timeout,
            )

            expected_path = os.path.join(
                temp_dir, f"bilibili_audio_{video_id}.mp3"
            )
            if os.path.exists(expected_path):
                logger.info(
                    f"[BilibiliAdapter] 音频下载成功: {expected_path}"
                )
                return expected_path

            for fname in os.listdir(temp_dir):
                if fname.startswith(f"bilibili_audio_{video_id}"):
                    fpath = os.path.join(temp_dir, fname)
                    logger.info(
                        f"[BilibiliAdapter] 音频下载成功: {fpath}"
                    )
                    return fpath

            logger.warning(
                f"[BilibiliAdapter] 音频下载后未找到文件: {video_id}"
            )
            return None

        except asyncio.TimeoutError:
            logger.error(
                f"[BilibiliAdapter] 音频下载超时 ({timeout}s): {video_id}"
            )
            return None
        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] 音频下载失败: {video_id} "
                f"{e}\n{traceback.format_exc()}"
            )
            return None

    @staticmethod
    def cleanup_audio(audio_path: str) -> None:
        """清理下载的临时音频文件。"""
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.debug(
                    f"[BilibiliAdapter] 已清理临时音频: {audio_path}"
                )
            except OSError as e:
                logger.warning(
                    f"[BilibiliAdapter] 清理音频失败: {audio_path} {e}"
                )

    # ── bilibili-api-python 实现 ───────────────────────────────────────────

    async def _fetch_metadata_via_api(
        self, video_id: str
    ) -> Optional[VideoMetadata]:
        """使用 bilibili-api-python 获取视频元信息（带 Cookie）。"""
        from bilibili_api import video, Credential

        credential = Credential(
            sessdata=self._sessdata, bili_jct=self._bili_jct
        )
        bvid = f"BV{video_id}"
        v = video.Video(bvid, credential=credential)

        try:
            info = await v.get_info()
            return VideoMetadata(
                video_id=video_id,
                title=info.get("title", ""),
                platform=self.name,
                description=info.get("desc", ""),
                duration=info.get("duration", 0),
                owner=info.get("owner", {}).get("name", ""),
                thumbnail_url=info.get("pic", ""),
                extra={"cid": await v.get_cid(0)},
            )
        except Exception as e:
            logger.warning(
                f"[BilibiliAdapter] bilibili-api 获取元信息异常: {e}"
            )
            return None

    async def _fetch_subtitles_via_api(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """使用 bilibili-api-python 获取视频字幕（带 Cookie）。"""
        from bilibili_api import video, Credential

        credential = Credential(
            sessdata=self._sessdata, bili_jct=self._bili_jct
        )
        bvid = f"BV{video_id}"
        v = video.Video(bvid, credential=credential)

        try:
            cid = await v.get_cid(0)
            subtitle_info = await v.get_subtitle(cid)

            if not subtitle_info or not subtitle_info.get("subtitles"):
                logger.info(
                    f"[BilibiliAdapter] bilibili-api: 视频 {video_id} 无字幕"
                )
                return None

            # 优先中文字幕
            target = None
            for sub in subtitle_info["subtitles"]:
                if sub.get("lan", "").startswith("zh"):
                    target = sub
                    break
            if not target:
                target = subtitle_info["subtitles"][0]

            subtitle_url = target.get("subtitle_url", "")
            if not subtitle_url:
                return None

            if not subtitle_url.startswith("http"):
                subtitle_url = "https:" + subtitle_url

            return await self._download_and_parse_subtitle(
                subtitle_url, max_length
            )

        except Exception as e:
            logger.warning(
                f"[BilibiliAdapter] bilibili-api 获取字幕异常: {e}"
            )
            return None

    # ── REST API 后备实现 ──────────────────────────────────────────────────

    async def _fetch_metadata_via_rest(
        self, video_id: str
    ) -> Optional[VideoMetadata]:
        """REST API 后备：获取视频元信息。"""
        api_url = (
            f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
        )
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers=BILIBILI_API_HEADERS,
            ) as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"[BilibiliAdapter] REST API 返回 {resp.status}"
                        )
                        return None
                    data = await resp.json()
                    if data.get("code") != 0:
                        logger.warning(
                            f"[BilibiliAdapter] REST API 错误: "
                            f"{data.get('message')}"
                        )
                        return None

                    result = data.get("data", {})
                    pages = result.get("pages", [])
                    cid = pages[0]["cid"] if pages else None

                    return VideoMetadata(
                        video_id=video_id,
                        title=result.get("title", ""),
                        platform=self.name,
                        description=result.get("desc", ""),
                        duration=result.get("duration", 0),
                        owner=result.get("owner", {}).get("name", ""),
                        thumbnail_url=result.get("pic", ""),
                        extra={"cid": cid},
                    )
        except aiohttp.ClientError as e:
            logger.error(f"[BilibiliAdapter] REST 网络错误: {e}")
            return None
        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] REST 获取元信息失败: "
                f"{e}\n{traceback.format_exc()}"
            )
            return None

    async def _fetch_subtitles_via_rest(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """REST API 后备：获取视频字幕。"""
        metadata = await self._fetch_metadata_via_rest(video_id)
        if not metadata:
            return None

        cid = metadata.extra.get("cid")
        if not cid:
            return None

        player_url = (
            f"https://api.bilibili.com/x/player/v2?bvid={video_id}&cid={cid}"
        )
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers=BILIBILI_API_HEADERS,
            ) as session:
                async with session.get(player_url) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if data.get("code") != 0:
                        return None

                    subtitle_info = (
                        data.get("data", {})
                        .get("subtitle", {})
                        .get("subtitles", [])
                    )
                    if not subtitle_info:
                        return None

                    subtitle_url = ""
                    for sub in subtitle_info:
                        lang = sub.get("lan", "")
                        if "zh" in lang or "ai" in lang.lower():
                            subtitle_url = sub.get("subtitle_url", "")
                            break
                    if not subtitle_url:
                        subtitle_url = subtitle_info[0].get(
                            "subtitle_url", ""
                        )
                    if not subtitle_url:
                        return None

                    if subtitle_url.startswith("//"):
                        subtitle_url = "https:" + subtitle_url

                return await self._download_and_parse_subtitle(
                    subtitle_url, max_length
                )

        except aiohttp.ClientError as e:
            logger.error(f"[BilibiliAdapter] REST 字幕网络错误: {e}")
            return None
        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] REST 字幕获取失败: "
                f"{e}\n{traceback.format_exc()}"
            )
            return None

    # ── 共享工具方法 ──────────────────────────────────────────────────────

    async def _download_and_parse_subtitle(
        self, subtitle_url: str, max_length: int
    ) -> Optional[str]:
        """下载并解析字幕 JSON 文件。"""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
            ) as session:
                async with session.get(subtitle_url) as resp:
                    if resp.status != 200:
                        return None
                    sub_data = await resp.json()
                    body = sub_data.get("body", [])
                    if not body:
                        return None

                    lines = [item.get("content", "") for item in body]
                    full_text = "\n".join(filter(None, lines))
                    if not full_text:
                        return None

                    if len(full_text) > max_length:
                        full_text = (
                            full_text[:max_length] + "\n...(字幕已截断)"
                        )
                        logger.info(
                            f"[BilibiliAdapter] 字幕过长 → 已截断至 {max_length}"
                        )

                    return full_text

        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] 字幕下载/解析失败: {e}"
            )
            return None
