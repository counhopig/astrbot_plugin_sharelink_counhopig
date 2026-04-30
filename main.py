"""
AstrBot 第三方分享链接解析插件（当前仅支持 Bilibili）。

功能：
- LLM Tool: bilibili_parse_link（供 Agent 自动调用）
"""

import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from platforms import BilibiliAdapter, PlatformRegistry


@register(
    "astrbot_plugin_sharelink_counhopig",
    "counhopig",
    "第三方分享链接解析插件（当前仅支持 Bilibili）",
    "1.0.0",
)
class ShareLinkParserPlugin(Star):
    """第三方分享链接解析插件。"""

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.response_mode = str(self.config.get("response_mode", "detailed")).lower()
        if self.response_mode not in {"detailed", "simple"}:
            self.response_mode = "detailed"
        self.include_description = bool(self.config.get("include_description", True))
        self.include_cover = bool(self.config.get("include_cover", True))
        self.description_max_length = int(self.config.get("description_max_length", 120))
        if self.description_max_length < 20:
            self.description_max_length = 20
        self._registry = PlatformRegistry()

    async def initialize(self):
        self._registry.register(BilibiliAdapter())
        logger.info(
            "[ShareLinkParser] 插件已加载 | 支持平台: %s | 输出模式: %s",
            ", ".join(self._registry.platforms),
            self.response_mode,
        )

    async def terminate(self):
        logger.info("[ShareLinkParser] 插件已卸载")

    @filter.llm_tool(name="bilibili_parse_link")
    async def bilibili_parse_link(self, event: AstrMessageEvent, target: str) -> str:
        """解析 B站分享链接并返回结构化信息。

        Args:
            target(string): B站链接、b23短链、BV号，或包含链接的文本。
        """
        extracted = self._extract_target(target or "")
        effective_target = extracted or (target or "").strip()
        if not effective_target:
            return "请输入有效的 B站链接、b23短链或 BV 号。"

        _, text = await self._parse_target_to_text(effective_target)
        return text

    async def _parse_target_to_text(self, target: str) -> tuple[bool, str]:
        """解析目标并返回 (是否成功, 输出文本)。"""
        adapter = self._registry.match(target)
        if not adapter:
            return (
                False,
                "暂不支持该链接。当前仅支持: %s" % ", ".join(self._registry.platforms),
            )

        resolved_url = await adapter.resolve_url(target)
        effective_target = resolved_url or target

        video_id = adapter.extract_id(effective_target)
        if not video_id:
            return False, "未识别出有效的视频 ID，请检查链接是否正确。"

        metadata = await adapter.fetch_metadata(video_id)
        if not metadata:
            return False, "解析失败：无法获取视频信息，可能是链接失效或视频不可访问。"

        canonical_url = adapter.get_video_url(video_id)
        duration_text = self._format_duration(metadata.duration)

        if self.response_mode == "simple":
            lines = [
                "解析结果",
                "标题: %s" % (metadata.title or "(无标题)"),
                "作者: %s" % (metadata.owner or "(未知)"),
                "链接: %s" % canonical_url,
            ]
        else:
            lines = [
                "解析结果",
                "平台: %s" % adapter.display_name,
                "标题: %s" % (metadata.title or "(无标题)"),
                "作者: %s" % (metadata.owner or "(未知)"),
                "时长: %s" % duration_text,
                "BV号: BV%s" % video_id,
                "规范链接: %s" % canonical_url,
            ]

        if resolved_url and resolved_url != target:
            lines.append("原始短链: %s" % target)

        if self.include_description and metadata.description:
            desc = metadata.description.strip().replace("\n", " ")
            if len(desc) > self.description_max_length:
                desc = desc[: self.description_max_length] + "..."
            lines.append("简介: %s" % desc)

        if self.include_cover and metadata.thumbnail_url:
            lines.append("封面: %s" % metadata.thumbnail_url)

        return True, "\n".join(lines)

    @staticmethod
    def _extract_target(message: str) -> str | None:
        """从消息中提取首个 URL，或提取裸 BV 号。"""
        url_match = re.search(r"https?://[^\s]+", message)
        if url_match:
            return url_match.group(0)

        bv_match = re.search(r"(?:bv|BV)([a-zA-Z0-9]{10})", message)
        if bv_match:
            return "BV" + bv_match.group(1)

        return None

    @staticmethod
    def _format_duration(seconds: int) -> str:
        if not seconds or seconds <= 0:
            return "未知"
        minutes, sec = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return "%d小时%d分%d秒" % (hours, minutes, sec)
        return "%d分%d秒" % (minutes, sec)

