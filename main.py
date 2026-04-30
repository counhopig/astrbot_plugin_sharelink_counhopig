"""
AstrBot 第三方分享链接解析插件（当前仅支持 Bilibili）。

功能：
- LLM Tool: bilibili_parse_link（供 Agent 自动调用）
"""

import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .platforms import BilibiliAdapter, PlatformRegistry


@register(
    "astrbot_plugin_sharelink_counhopig",
    "counhopig",
    "第三方分享链接解析插件（当前仅支持 Bilibili）",
        "1.3.0",
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
        self.CHUNK_SIZE = 4000
        self._content_cache: dict[str, str] = {}
        self.summarize_provider_id = str(
            self.config.get("summarize_provider_id", "")
        ).strip()
        self.stt_provider_id = str(
            self.config.get("stt_provider_id", "")
        ).strip()

    async def initialize(self):
        # 读取 B站 Cookie 配置
        bilibili_cookie = self.config.get("bilibili_cookie", {})
        sessdata = ""
        bili_jct = ""
        if isinstance(bilibili_cookie, dict):
            sessdata = str(bilibili_cookie.get("sessdata", "")).strip()
            bili_jct = str(bilibili_cookie.get("bili_jct", "")).strip()

        self._registry.register(
            BilibiliAdapter(sessdata=sessdata, bili_jct=bili_jct)
        )
        logger.info(
            "[ShareLinkParser] 插件已加载 | 支持平台: %s | 输出模式: %s",
            ", ".join(self._registry.platforms),
            self.response_mode,
        )

    async def terminate(self):
        logger.info("[ShareLinkParser] 插件已卸载")

    @filter.llm_tool(name="bilibili_parse_link")
    async def bilibili_parse_link(
        self, event: AstrMessageEvent, target: str
    ) -> str:
        """解析 B站分享链接并返回结构化信息。

        Args:
            target(string): B站链接、b23短链、BV号，或包含链接的文本。
        """
        extracted = self._extract_target(target or "")
        effective_target = extracted or (target or "").strip()
        if not effective_target:
            return "请输入有效的 B站链接、b23短链或 BV 号。"

        _, text = await self._parse_target_to_text(event, effective_target)
        return text

    async def _parse_target_to_text(
        self, event: AstrMessageEvent, target: str
    ) -> tuple[bool, str]:
        """解析目标并返回 (是否成功, 输出文本)。"""
        adapter = self._registry.match(target)
        if not adapter:
            return (
                False,
                "暂不支持该链接。当前仅支持: %s"
                % ", ".join(self._registry.platforms),
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

        # ── 字幕 / 音频转录 ──────────────────────────────────────────────
        content_text = await self._fetch_content_with_fallback(
            event, adapter, video_id
        )
        if content_text:
            self._content_cache[video_id] = content_text
            # 优先用 LLM 内部总结；失败则回退到原始字幕
            summarized = await self._summarize_content(
                event, content_text
            )
            lines.append("")
            lines.append("---")
            lines.append("视频内容:")
            lines.append(summarized or content_text)

        return True, "\n".join(lines)

    async def _fetch_content_with_fallback(
        self,
        event: AstrMessageEvent,
        adapter,
        video_id: str,
    ) -> str | None:
        """尝试获取视频内容：先字幕，失败则下载音频并用 STT 转录。"""
        # 1. 尝试获取字幕
        try:
            subtitles = await adapter.fetch_subtitles(video_id, max_length=500000)
            if subtitles:
                logger.info(
                    "[ShareLinkParser] 字幕获取成功: %s (%d 字符)",
                    video_id,
                    len(subtitles),
                )
                return subtitles
        except Exception as e:
            logger.warning(
                "[ShareLinkParser] 字幕获取异常: %s %s", video_id, e
            )

        # 2. 字幕不可用，尝试下载音频
        logger.info(
            "[ShareLinkParser] 字幕不可用，尝试下载音频: %s", video_id
        )
        audio_path = None
        try:
            audio_path = await adapter.download_audio(video_id)
        except Exception as e:
            logger.error(
                "[ShareLinkParser] 音频下载异常: %s %s", video_id, e
            )

        if not audio_path:
            logger.warning(
                "[ShareLinkParser] 音频下载失败，无法获取内容: %s",
                video_id,
            )
            return None

        # 3. 使用 AstrBot STT 转录音频
        transcribed = None
        try:
            if self.stt_provider_id:
                stt_provider = self.context.get_provider_by_id(
                    self.stt_provider_id
                )
            else:
                stt_provider = self.context.get_using_stt_provider(
                    umo=event.unified_msg_origin
                )
            if stt_provider:
                logger.info(
                    "[ShareLinkParser] 使用 STT 转录音频: %s", audio_path
                )
                transcribed = await stt_provider.get_text(audio_path)
                if transcribed:
                    logger.info(
                        "[ShareLinkParser] STT 转录成功: %s (%d 字符)",
                        video_id,
                        len(transcribed),
                    )
            else:
                logger.warning(
                    "[ShareLinkParser] 未配置 STT Provider，"
                    "跳过音频转录: %s",
                    video_id,
                )
        except Exception as e:
            logger.error(
                "[ShareLinkParser] STT 转录失败: %s %s", video_id, e
            )
        finally:
            # 无论成功与否，清理临时音频
            if hasattr(adapter, "cleanup_audio"):
                adapter.cleanup_audio(audio_path)

        return transcribed

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

    async def _summarize_content(
        self, event: AstrMessageEvent, content_text: str
    ) -> str | None:
        """调用 LLM 对视频字幕进行总结。内容过长时内部分页处理。"""
        if not self.summarize_provider_id:
            return None

        try:
            # 短内容直接一次性总结
            if len(content_text) <= 12000:
                return await self._llm_summarize_once(
                    event, content_text
                )

            # 长内容：内部分页 → 分段提取要点 → 合并总结
            return await self._llm_summarize_long(
                event, content_text
            )
        except Exception as e:
            logger.warning(
                "[ShareLinkParser] LLM 总结失败，回退到原始字幕: %s", e
            )
            return None

    async def _llm_summarize_once(
        self, event: AstrMessageEvent, text: str
    ) -> str:
        """一次性总结（适用于短内容）。"""
        prompt = (
            "请对以下视频字幕内容进行总结，提取核心要点。\n\n"
            f"字幕内容：\n{text}\n\n"
            "要求：\n"
            "1. 先给出 2-3 句话的整体概要\n"
            "2. 再列出 3-5 个关键要点\n"
            "3. 保持客观中立，不要添加个人评价\n"
            "4. 使用中文输出"
        )

        resp = await self.context.llm_generate(
            chat_provider_id=self.summarize_provider_id,
            prompt=prompt,
        )
        return resp.completion_text or ""

    async def _llm_summarize_long(
        self, event: AstrMessageEvent, text: str
    ) -> str:
        """长内容分页总结：分段提取要点后合并。"""
        chunk_size = 8000
        chunks = [
            text[i : i + chunk_size]
            for i in range(0, len(text), chunk_size)
        ]

        logger.info(
            "[ShareLinkParser] 字幕较长 (%d 字符)，分 %d 段总结",
            len(text),
            len(chunks),
        )

        # 1. Map：每段提取要点
        summaries: list[str] = []
        for idx, chunk in enumerate(chunks, 1):
            prompt = (
                f"这是视频字幕的第 {idx}/{len(chunks)} 部分，"
                f"请提取其中的关键信息要点：\n\n{chunk}\n\n"
                "要求：只输出要点列表，不要输出总结性语句。"
            )
            resp = await self.context.llm_generate(
                chat_provider_id=self.summarize_provider_id,
                prompt=prompt,
            )
            part = (resp.completion_text or "").strip()
            if part:
                summaries.append(part)

        if not summaries:
            return ""

        # 2. Reduce：合并所有要点生成最终总结
        merged = "\n\n".join(
            f"【第 {i + 1} 部分要点】\n{s}"
            for i, s in enumerate(summaries)
        )
        final_prompt = (
            "以下是视频各分段提取的要点，请整合为一份完整的视频总结：\n\n"
            f"{merged}\n\n"
            "要求：\n"
            "1. 先给出 2-3 句话的整体概要\n"
            "2. 再列出 3-5 个关键要点\n"
            "3. 保持客观中立\n"
            "4. 使用中文输出"
        )
        resp = await self.context.llm_generate(
            chat_provider_id=self.summarize_provider_id,
            prompt=final_prompt,
        )
        return resp.completion_text or ""

