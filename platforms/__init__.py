"""
多平台视频总结适配器

用法:
    from platforms import BilibiliAdapter, PlatformRegistry
    registry = PlatformRegistry()
    registry.register(BilibiliAdapter())
    adapter = registry.match(url)
"""

from .base import BasePlatformAdapter, VideoMetadata
from .registry import PlatformRegistry
from .bilibili import BilibiliAdapter

from .youtube import YouTubeAdapter

__all__ = [
    "BasePlatformAdapter",
    "VideoMetadata",
    "PlatformRegistry",
    "BilibiliAdapter",
    "YouTubeAdapter",
]
