"""
Bilibili（B站）平台适配器。

将原 main.py 中所有 B站相关逻辑迁移至此处，
包括 URL 解析、视频信息获取、字幕提取等。
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

# ─── yt-dlp 懒加载 ───────────────────────────────────────────────────────────

_yt_dlp = None


def _get_yt_dlp():
    global _yt_dlp
    if _yt_dlp is None:
        import yt_dlp

        _yt_dlp = yt_dlp
    return _yt_dlp


class BilibiliAdapter(BasePlatformAdapter):
    """Bilibili（B站）视频适配器。"""

    @property
    def name(self) -> str:
        return "bilibili"

    @property
    def display_name(self) -> str:
        return "B站"

    # ── URL 匹配与解析 ────────────────────────────────────────────────────

    def match(self, url: str) -> bool:
        """判断 URL 是否为 B站链接或纯 BV/AV 号。"""
        # 纯 BV/AV 号
        if BVID_PATTERN.search(url) or AVID_PATTERN.search(url):
            return True
        # 完整 URL
        try:
            parsed = urlparse(url)
            if "bilibili.com" in parsed.netloc or "b23.tv" in parsed.netloc:
                return True
        except Exception:
            pass
        return False

    def extract_id(self, url: str) -> Optional[str]:
        """从 URL 或纯 ID 中提取 BV 号（不含 BV 前缀）。

        支持格式:
        - BV1xx4x1x7xx
        - https://www.bilibili.com/video/BV1xx4x1x7xx
        - https://b23.tv/xxxxx（需先 resolve_url）
        - av123456（会转为 BV，但 API 不保证支持，优先 BV）
        """
        match = BVID_PATTERN.search(url)
        if match:
            return match.group(1)
        # AV 号暂不转换，返回 None（B站 API 已逐步弃用 AV 号）
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
        """从 B站 API 获取视频元信息。

        Args:
            video_id: BV 号（不含 BV 前缀），如 "1xx4x1x7xx"。
        """
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers=BILIBILI_API_HEADERS,
            ) as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"[BilibiliAdapter] API 返回 {resp.status}"
                        )
                        return None
                    data = await resp.json()
                    if data.get("code") != 0:
                        logger.warning(
                            f"[BilibiliAdapter] API 错误: {data.get('message')}"
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
            logger.error(f"[BilibiliAdapter] 网络错误: {e}")
            return None
        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] 获取视频信息失败: "
                f"{e}\n{traceback.format_exc()}"
            )
            return None

    async def fetch_subtitles(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """从 B站 API 获取视频字幕文本。

        Args:
            video_id: BV 号（不含 BV 前缀）。
            max_length: 最大字符数，超出截断。
        """
        # 需要先获取 cid
        metadata = await self.fetch_metadata(video_id)
        if not metadata:
            return None

        cid = metadata.extra.get("cid")
        if not cid:
            return None

        return await self._fetch_subtitle_by_cid(video_id, cid, max_length)

    async def fetch_subtitles_with_cid(
        self, video_id: str, cid: int, max_length: int = 4000
    ) -> Optional[str]:
        """直接使用 cid 获取字幕（避免重复请求元信息）。

        当已经通过 fetch_metadata 拿到 cid 时，应使用此方法。
        """
        return await self._fetch_subtitle_by_cid(video_id, cid, max_length)

    def get_video_url(self, video_id: str) -> str:
        """返回 B站视频完整 URL（供 yt-dlp 使用）。"""
        return f"https://www.bilibili.com/video/BV{video_id}"

    async def download_audio(
        self, video_id: str, timeout: int = 300
    ) -> Optional[str]:
        """使用 yt-dlp 下载视频音频作为字幕后备方案。

        Args:
            video_id: BV 号（不含 BV 前缀）。
            timeout: 下载超时秒数。

        Returns:
            下载的音频文件本地路径（m4a 格式），失败返回 None。
        """
        try:
            yt_dlp = _get_yt_dlp()
        except ImportError:
            logger.error(
                "[BilibiliAdapter] yt-dlp 未安装，"
                "请执行: pip install yt-dlp"
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
                    "preferredcodec": "m4a",
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
                temp_dir, f"bilibili_audio_{video_id}.m4a"
            )
            if os.path.exists(expected_path):
                logger.info(
                    f"[BilibiliAdapter] 音频下载成功: {expected_path}"
                )
                return expected_path

            # 兜底查找
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

    # ── 内部方法 ──────────────────────────────────────────────────────────

    async def _fetch_subtitle_by_cid(
        self, bvid: str, cid: int, max_length: int
    ) -> Optional[str]:
        """通过 BV号 + cid 获取字幕文本。"""
        player_url = (
            f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
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

                    # 优先中文字幕，其次 AI 字幕
                    subtitle_url = ""
                    for sub in subtitle_info:
                        lang = sub.get("lan", "")
                        if "zh" in lang or "ai" in lang.lower():
                            subtitle_url = sub.get("subtitle_url", "")
                            break
                    if not subtitle_url:
                        subtitle_url = subtitle_info[0].get("subtitle_url", "")
                    if not subtitle_url:
                        return None

                    if subtitle_url.startswith("//"):
                        subtitle_url = "https:" + subtitle_url

                async with session.get(subtitle_url) as sub_resp:
                    if sub_resp.status != 200:
                        return None
                    sub_data = await sub_resp.json()
                    body = sub_data.get("body", [])
                    if not body:
                        return None

                    lines = [item.get("content", "") for item in body]
                    full_text = "\n".join(filter(None, lines))
                    if not full_text:
                        return None

                    if len(full_text) > max_length:
                        full_text = full_text[:max_length] + "\n...(字幕已截断)"
                        logger.info(
                            f"[BilibiliAdapter] 字幕过长 → 已截断至 {max_length}"
                        )

                    return full_text

        except aiohttp.ClientError as e:
            logger.error(f"[BilibiliAdapter] 字幕获取网络错误: {e}")
            return None
        except Exception as e:
            logger.error(
                f"[BilibiliAdapter] 字幕获取失败: "
                f"{e}\n{traceback.format_exc()}"
            )
            return None
