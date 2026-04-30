# 更新日志

本项目所有值得注意的更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，本项目遵循 [语义化版本规范](https://semver.org/spec/v2.0.0.html)。

## [1.3.0] - 2026-05-01

### 新增
- **LLM 内部总结**：新增 `summarize_provider_id` 配置项，支持指定 LLM Provider 在插件内部自动总结视频字幕。短内容（≤12000 字符）直接一次性总结；长内容自动内部分页（Map-Reduce），分段提取要点后合并为完整总结。
- **STT Provider 可选**：新增 `stt_provider_id` 配置项，支持指定专门的 STT Provider 用于音频转录。留空则使用当前会话默认 STT Provider。
- 配置 schema 支持 `"_special": "select_provider"` / `"select_provider_stt"`，WebUI 中显示 Provider 下拉选择框。

### 变更
- 字幕获取上限从 4000 提升至 500000 字符，确保长视频完整字幕进入插件。
- 移除外部 Agent 续读机制，长内容处理完全内聚在插件中。
- 音频下载格式从 m4a 改为 mp3，提升 STT 兼容性（部分 Provider 如 MiMo 不支持 m4a）。

## [1.2.0] - 2026-05-01

### 新增
- **bilibili-api-python 集成**：优先使用 `bilibili-api-python` 官方库获取视频信息和字幕，REST API 作为后备。
- **B站 Cookie 鉴权**：可配置 `SESSDATA` / `bili_jct`，显著提升字幕获取成功率（需登录才能获取的字幕现在也能拿到）。

### 变更
- `BilibiliAdapter` 构造函数支持可选的 Cookie 参数。
- 字幕获取使用 `bilibili-api` 的 `video.get_subtitle()` 方法，语言匹配逻辑与 biliread 对齐。

## [1.1.0] - 2026-05-01

### 新增
- `bilibili_parse_link` LLM 工具在可用时返回**视频字幕**。
- **音频下载 + STT 回退**：当字幕不可用时，插件自动通过 yt-dlp 下载视频音频，并使用 AstrBot 配置的 STT Provider 进行转录。
- 添加 `yt-dlp` 作为音频提取的依赖。

## [1.0.0] - 2026-05-01

### 新增
- AstrBot 分享链接解析插件初始版本发布。
- 支持 B站链接解析，包括：
  - 完整 URL（`bilibili.com/video/BV...`）
  - 短链接（`b23.tv`）
  - 纯 BV 号
  - 短链接解析为完整 URL
  - 元数据提取（标题、作者、时长、简介、封面）
  - 字幕获取支持
- YouTube 适配器预览，支持元数据和字幕提取。
- LLM 工具 `bilibili_parse_link`，供 Agent 自动解析链接。
- 聊天消息中自动检测 B站链接。
- 配置 schema 支持以下选项：
  - `auto_detect`：启用/禁用自动链接检测
  - `response_mode`：`detailed`（详细）或 `simple`（简洁）输出格式
  - `include_description`：显示/隐藏视频简介
  - `include_cover`：显示/隐藏封面图 URL
  - `description_max_length`：在指定长度处截断简介
