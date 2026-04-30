"""
平台适配器注册中心。

支持多平台同时启用，URL 到来自动匹配对应适配器。
"""

from __future__ import annotations

from typing import Optional

from astrbot.api import logger

from .base import BasePlatformAdapter


class PlatformRegistry:
    """平台适配器注册中心。

    用法::

        registry = PlatformRegistry()
        registry.register(BilibiliAdapter())
        adapter = registry.match("https://www.bilibili.com/video/BV1xx4x1x7xx")
        if adapter:
            video_id = adapter.extract_id(url)
    """

    def __init__(self) -> None:
        self._adapters: list[BasePlatformAdapter] = []

    def register(self, adapter: BasePlatformAdapter) -> None:
        """注册一个平台适配器。

        后注册的适配器优先级更高（匹配时从后往前遍历）。
        """
        self._adapters.append(adapter)
        logger.info(
            f"[PlatformRegistry] 已注册平台适配器: "
            f"{adapter.display_name} ({adapter.name})"
        )

    def unregister(self, name: str) -> bool:
        """按 name 移除已注册的适配器，成功返回 True。"""
        for i, adapter in enumerate(self._adapters):
            if adapter.name == name:
                self._adapters.pop(i)
                return True
        return False

    def match(self, url: str) -> Optional[BasePlatformAdapter]:
        """从已注册的适配器中找到第一个能处理该 URL 的。

        遍历顺序为注册顺序（先注册先匹配），找到即返回。
        """
        for adapter in self._adapters:
            if adapter.match(url):
                return adapter
        return None

    @property
    def platforms(self) -> list[str]:
        """返回所有已注册平台的 name 列表。"""
        return [a.name for a in self._adapters]
