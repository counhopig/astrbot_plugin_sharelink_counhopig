# astrbot_plugin_sharelink_counhopig

AstrBot 第三方分享链接解析插件，当前主要支持 Bilibili（B站）链接解析，同时包含 YouTube 适配器预览。

## 功能特性

- **自动检测**：自动识别聊天中的 B站链接、BV号或 b23.tv 短链
- **LLM 工具**：提供 `bilibili_parse_link` 工具，供 Agent 自动调用解析链接
- **多输出模式**：支持 `detailed`（详细）和 `simple`（简洁）两种输出格式
- **字幕获取**：支持获取 B站视频字幕（含 AI 生成字幕）
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

## 配置

在 AstrBot 管理面板中配置以下选项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `auto_detect` | boolean | `true` | 自动检测并解析聊天中的 B站链接 |
| `response_mode` | string | `"detailed"` | 输出模式：`detailed`（详细）或 `simple`（简洁） |
| `include_description` | boolean | `true` | 是否在解析结果中包含视频简介 |
| `include_cover` | boolean | `true` | 是否在解析结果中包含封面图链接 |
| `description_max_length` | integer | `120` | 简介最大输出长度（最小 20） |

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

## 支持的链接格式

- B站完整链接：`https://www.bilibili.com/video/BV1xx4x1x7xx`
- B站短链：`https://b23.tv/xxxxx`
- 纯 BV 号：`BV1xx4x1x7xx`
- YouTube 链接（预览）：`https://www.youtube.com/watch?v=xxxxx`

## 依赖

- `aiohttp>=3.8.0`
- AstrBot >= 4.0.0

### 可选依赖（YouTube 支持）

- `yt-dlp`（用于 YouTube 元信息获取）
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

## 许可证

MIT License

## 作者

- **counhopig**
- GitHub: [@counhopig](https://github.com/counhopig)

## 致谢

感谢 [AstrBot](https://github.com/AstrBot/AstrBot) 提供的机器人框架支持。
