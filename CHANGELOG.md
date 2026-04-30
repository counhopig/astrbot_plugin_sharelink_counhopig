# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-05-01

### Fixed
- Fix module import error by changing `from platforms import ...` to `from .platforms import ...` in `main.py`. This resolves the `No module named 'platforms'` error when AstrBot loads the plugin.

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
