# AstrBot 分享链接解析插件

> 🤖 **本插件的全部代码、架构设计、功能规划与文档，均由 AI（GitHub Copilot · Claude Sonnet）全程管理和撰写，作者仅提供产品方向与验收。**

AstrBot 第三方分享链接解析插件，当前主要支持 Bilibili（B站）链接解析，同时包含 YouTube 适配器预览。

## 功能特性

- **自动检测**：自动识别聊天中的 B站链接、BV号或 b23.tv 短链
- **LLM 工具**：提供 `bilibili_parse_link` 工具，供 Agent 自动调用解析链接
- **多输出模式**：支持 `detailed`（详细）和 `simple`（简洁）两种输出格式
- **字幕获取**：支持获取 B站视频字幕（含 AI 生成字幕），支持 Cookie 鉴权获取高质量字幕
- **音频降级**：字幕不可用时，自动下载音频并通过 AstrBot STT 转文字
- **平台适配器架构**：基于 `BasePlatformAdapter` 的扩展架构，易于新增平台支持

## 安装

### 方式一：通过 AstrBot 插件市场安装

在 AstrBot 控制台中搜索 `astrbot_plugin_sharelink_counhopig` 并安装。

### 方式二：手动安装

```bash
# 进入 AstrBot 插件目录
cd AstrBot/data/plugins

# 克隆仓库
git clone https://github.com/counhopig/astrbot_plugin_sharelink_counhopig.git

# 安装依赖
pip install -r astrbot_plugin_sharelink_counhopig/requirements.txt
```

然后重启 AstrBot。

## 配置项

在 AstrBot 管理后台的插件配置页面中进行配置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `auto_detect` | boolean | `true` | 自动检测并解析聊天中的 B站链接 |
| `response_mode` | string | `"detailed"` | 输出模式：`detailed`（详细）或 `simple`（简洁） |
| `include_description` | boolean | `true` | 是否在解析结果中包含视频简介 |
| `include_cover` | boolean | `true` | 是否在解析结果中包含封面图链接 |
| `description_max_length` | integer | `120` | 简介最大输出长度（最小 20） |
| `bilibili_cookie.sessdata` | string | `""` | B站 SESSDATA，用于获取高质量字幕 |
| `bilibili_cookie.bili_jct` | string | `""` | B站 bili_jct（可选） |
| `summarize_provider_id` | string | `""` | 总结视频的 AI 模型。指定 LLM Provider 在插件内部自动总结字幕；留空则直接返回原始字幕 |
| `stt_provider_id` | string | `""` | 音频转文字的 STT 模型。指定 STT Provider 用于字幕不可用时下载音频转录；留空则使用当前会话默认 STT Provider |

### B站 Cookie 配置

由于 B站部分视频信息及字幕接口需要登录态，请提供你账号的 Cookie 信息。插件需要其中的 `SESSDATA` 和 `bili_jct` 字段。

> ⚠️ **重要**：Cookie 是敏感信息，请勿泄露给他人。插件仅在本地使用，不会上传或分享你的 Cookie。

#### 方法一：使用浏览器插件获取（推荐新手）

1. 安装 **Cookie Editor** 浏览器插件（[Chrome](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) / [Firefox](https://addons.mozilla.org/zh-CN/firefox/addon/cookie-editor/)）
2. 在浏览器中登录 [Bilibili](https://www.bilibili.com)
3. 点击 Cookie Editor 图标，搜索 `SESSDATA`，复制其值
4. 同样搜索 `bili_jct`，复制其值
5. 进入 AstrBot 后台 → 插件配置 → 分享链接解析，将复制的值分别填入 `bilibili_cookie.sessdata` 和 `bilibili_cookie.bili_jct`

#### 方法二：使用开发者工具获取

1. 在电脑端浏览器登录 [Bilibili](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具，切换到 **应用**（Application）标签页
3. 左侧找到 **存储** → **Cookie** → `https://www.bilibili.com`
4. 在列表中查找 `SESSDATA` 和 `bili_jct` 字段，复制它们的值
5. 填入 AstrBot 插件配置的对应输入框中

## 使用方法

### 自动检测（默认开启）

当 `auto_detect` 为 `true` 时，插件会自动检测聊天消息中的 B站链接并返回解析结果：

```
用户: https://www.bilibili.com/video/BV1xx4x1x7xx
Bot: 正在解析链接，请稍候...
Bot: 解析结果
平台: B站
标题: 视频标题
作者: UP主名称
时长: 5分30秒
BV号: BV1xx4x1x7xx
规范链接: https://www.bilibili.com/video/BV1xx4x1x7xx
简介: 视频简介内容...
封面: https://...
```

### LLM 工具调用

当 AstrBot 启用 Agent 模式时，LLM 可以自动调用 `bilibili_parse_link` 工具解析链接。

### 支持的链接格式

- B站完整链接：`https://www.bilibili.com/video/BV1xx4x1x7xx`
- B站短链：`https://b23.tv/xxxxx`
- 纯 BV 号：`BV1xx4x1x7xx`
- YouTube 链接（预览）：`https://www.youtube.com/watch?v=xxxxx`

## 依赖

- `aiohttp>=3.8.0`
- `bilibili-api-python>=17.0.0`
- `yt-dlp>=2024.0.0`（用于音频下载降级）
- AstrBot >= 4.0.0

### 可选依赖（YouTube 支持）

- `youtube-transcript-api`（用于 YouTube 字幕获取）

## 项目结构

```
astrbot_plugin_sharelink_counhopig/
├── main.py                 # 插件主入口
├── metadata.yaml           # 插件元数据
├── requirements.txt        # Python 依赖
├── _conf_schema.json       # 配置项定义
├── CHANGELOG.md            # 更新日志
├── README.md               # 项目说明
├── .gitignore              # Git 忽略规则
└── platforms/              # 平台适配器
    ├── __init__.py
    ├── base.py             # 抽象基类
    ├── registry.py         # 适配器注册中心
    ├── bilibili.py         # B站适配器
    └── youtube.py          # YouTube 适配器（预览）
```

## 开发计划

- [ ] 支持更多平台（抖音、小红书等）
- [ ] 支持视频内容总结
- [ ] 完善 YouTube 适配器

## 开源协议

MIT License
