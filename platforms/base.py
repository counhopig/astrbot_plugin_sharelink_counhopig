"""
平台适配器抽象基类与统一数据结构。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoMetadata:
    """视频元信息，所有平台适配器统一返回此结构。"""

    # ── 必填字段 ──────────────────────────────────────────────────────────
    video_id: str          # 平台内部 ID（B站为 BV号去掉前缀，如 "1xx4x1x7xx"）
    title: str             # 视频标题
    platform: str          # 平台标识，如 "bilibili"、"youtube"

    # ── 可选字段 ──────────────────────────────────────────────────────────
    description: str = ""          # 视频简介
    duration: int = 0              # 时长（秒）
    owner: str = ""                # 作者/UP主
    thumbnail_url: str = ""        # 封面图 URL
    extra: dict = field(default_factory=dict)  # 平台特有字段（如 B站 cid）


class BasePlatformAdapter(abc.ABC):
    """平台适配器抽象基类。

    每个视频平台实现此接口，提供 URL 匹配、ID 提取、元信息获取、
    字幕提取等能力。插件核心流程通过统一接口调用，无需关心平台差异。
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """平台唯一标识，如 'bilibili'、'youtube'。"""

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """平台显示名称，如 'B站'、'YouTube'。"""

    # ── URL 匹配与解析 ────────────────────────────────────────────────────

    @abc.abstractmethod
    def match(self, url: str) -> bool:
        """判断是否支持该 URL 或纯 ID。

        Args:
            url: 用户消息中提取的链接或纯 ID（如 "BV1xx4x1x7xx"）。

        Returns:
            True 表示本平台可以处理该链接。
        """

    @abc.abstractmethod
    def extract_id(self, url: str) -> Optional[str]:
        """从 URL 或纯 ID 中提取平台视频 ID。

        Args:
            url: 原始链接或纯 ID 字符串。

        Returns:
            平台视频 ID，无法识别时返回 None。
        """

    async def resolve_url(self, url: str) -> Optional[str]:
        """解析短链接 / 重定向链接，返回规范化完整 URL。

        默认实现直接返回 None（无需解析）。B站等有短链接的平台应覆盖此方法。

        Args:
            url: 原始短链接。

        Returns:
            解析后的完整 URL，解析失败返回 None。
        """
        return None

    # ── 数据获取 ──────────────────────────────────────────────────────────

    @abc.abstractmethod
    async def fetch_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """获取视频元信息。

        Args:
            video_id: 平台视频 ID（由 extract_id 返回）。

        Returns:
            VideoMetadata 实例，获取失败返回 None。
        """

    @abc.abstractmethod
    async def fetch_subtitles(
        self, video_id: str, max_length: int = 4000
    ) -> Optional[str]:
        """获取视频字幕 / 文本内容。

        Args:
            video_id: 平台视频 ID。
            max_length: 最大字符数，超出截断。

        Returns:
            字幕文本，无字幕或失败返回 None。
        """

    @abc.abstractmethod
    def get_video_url(self, video_id: str) -> str:
        """获取可直接播放/下载的视频 URL（供 yt-dlp 使用）。

        Args:
            video_id: 平台视频 ID。

        Returns:
            完整视频 URL。
        """
