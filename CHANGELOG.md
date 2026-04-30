# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-05-01

### Added
- **LLM 内部总结**：新增 `summarize_provider_id` 配置项，支持指定 LLM Provider 在插件内部自动总结视频字幕。短内容（≤12000 字符）直接一次性总结；长内容自动内部分页（Map-Reduce），分段提取要点后合并为完整总结。
- **STT Provider 可选**：新增 `stt_provider_id` 配置项，支持指定专门的 STT Provider 用于音频转录。留空则使用当前会话默认 STT Provider。
- 配置 schema 支持 `"_special": "select_provider"` / `"select_provider_stt"`，WebUI 中显示 Provider 下拉选择框。

### Changed
- 字幕获取上限从 4000 提升至 500000 字符，确保长视频完整字幕进入插件。
- 移除外部 Agent 续读机制，长内容处理完全内聚在插件中。
- 音频下载格式从 m4a 改为 mp3，提升 STT 兼容性（部分 Provider 如 MiMo 不支持 m4a）。

## [1.2.0] - 2026-05-01

### Added
- **bilibili-api-python 集成**：优先使用 `bilibili-api-python` 官方库获取视频信息和字幕，REST API 作为后备。
- **B站 Cookie 鉴权**：可配置 `SESSDATA` / `bili_jct`，显著提升字幕获取成功率（需登录才能获取的字幕现在也能拿到）。

### Changed
- `BilibiliAdapter` 构造函数支持可选的 Cookie 参数。
- 字幕获取使用 `bilibili-api` 的 `video.get_subtitle()` 方法，语言匹配逻辑与 biliread 对齐。

## [1.1.0] - 2026-05-01

### Added
- `bilibili_parse_link` LLM tool now returns **video subtitles** when available.
- **Audio download + STT fallback**: When subtitles are unavailable, the plugin automatically downloads the video audio via yt-dlp and transcribes it using AstrBot's configured STT provider.
- Added `yt-dlp` as a dependency for audio extraction.

## [1.0.0] - 2026-05-01

### Added
- Initial release of AstrBot share link parser plugin.
- Support Bilibili link parsing including:
  - Full URLs (`bilibili.com/video/BV...`)
  - Short links (`b23.tv`)
  - Raw BV IDs
  - Short link resolution to full URL
  - Metadata extraction (title, author, duration, description, thumbnail)
  - Subtitle fetching support
- YouTube adapter preview with metadata and subtitle extraction support.
- LLM tool `bilibili_parse_link` for automatic link parsing by agent.
- Auto-detection of Bilibili links in chat messages.
- Configuration schema with options:
  - `auto_detect`: Enable/disable automatic link detection
  - `response_mode`: `detailed` or `simple` output format
  - `include_description`: Show/hide video description
  - `include_cover`: Show/hide cover image URL
  - `description_max_length`: Truncate description at specified length
