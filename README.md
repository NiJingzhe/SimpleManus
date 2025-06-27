# SimpleAgent

一个极其简单的通用单智能体框架，类似于 OpenManus 但更易于开发和使用。基于 SimpleLLMFunc 构建。

## 🎯 项目简介

SimpleAgent 是一个通用的智能助手框架，具有高度的可扩展性和定制化能力。框架集成了对话管理、工具调用、上下文保存和智能存储等核心功能。

**当前实现** 针对 CAD 建模进行了专门优化，提供从概念设计到代码实现的全流程建模支持。但通过简单地修改 Prompt 和 Tools，可以轻松适配到其他任何专业领域，如：
- 代码开发助手
- 数据分析专家  
- 文档写作助手
- 科研工具集成
- 业务流程自动化
- 等等...

## ✨ 主要特性

### 🏗️ 通用框架架构
- **高度可扩展**: 通过修改 Prompt 和 Tools 快速适配不同领域
- **模块化设计**: 核心组件与业务逻辑分离，便于定制化开发
- **领域无关**: 框架本身不绑定特定业务，可应用于任何专业场景
- **快速部署**: 简单配置即可构建专业级智能助手

### 🤖 智能对话系统
- **多模型支持**: 集成 GPT-4o、Claude、Gemini、DeepSeek 等多种 LLM
- **流式对话**: 实时响应，支持打字机效果的流式输出
- **上下文保持**: 自动管理对话历史，支持长期记忆和摘要
- **会话管理**: 支持历史查询、导出、清空等操作

### 🛠️ 专业工具集
- **需求细化**: 将模糊需求转化为详细建模规范
- **代码生成**: 生成高质量的 CADQuery Python 代码
- **文件操作**: 智能文件读写，支持语义化路径管理
- **命令执行**: 安全的系统命令执行环境
- **3D 渲染**: 多视角模型渲染和可视化验证

### 📒 SketchPad 智能存储系统
- **智能缓存**: LRU 缓存机制，自动管理存储空间
- **标签管理**: 支持多标签分类和智能检索
- **自动摘要**: AI 自动生成内容摘要，便于查找
- **持久化**: 支持数据持久化存储和恢复

### 🎨 CAD 建模专业化（当前实现示例）
- **七步建模流程**: 标准化的 CAD 建模工作流
- **语义化文件组织**: 自动创建结构化的项目文件夹
- **多格式支持**: 支持 STEP、STL 等主流 CAD 格式
- **可视化验证**: 自动生成多视角渲染图进行设计验证

> 💡 **扩展提示**: 通过替换专业 Prompt 和工具集，可快速改造为其他领域的专业助手

## 🚀 快速开始

### 环境要求

- Python 3.10+
- CADQuery 2.5.2+
- 支持的操作系统: macOS, Linux, Windows

### 安装依赖

```bash
# 使用 uv 安装依赖（推荐）
uv sync
```

### 配置设置

1. 复制配置模板：
```bash
cp config/provider_template.json config/provider.json
```

2. 编辑 `config/provider.json`，填入您的 API 密钥：
```json
{
  "chatanywhere": {
    "gpt-4o": {
      "api_key": "your-api-key-here",
      "base_url": "https://api.chatanywhere.tech/v1"
    }
  }
}
```

### 启动应用

```bash
python main.py
```

## 🔄 框架定制化

### 快速适配其他领域

SimpleAgent 的设计理念是"一次开发，多域复用"。要将框架适配到新的专业领域，只需要：

#### 1. 修改 Agent Prompt
编辑 `agent/BaseAgent.py` 中的 `chat_impl` 函数内的系统提示词：

```python
def chat_impl(history, query, time, sketch_pad_summary):
    """
    # 🎯 身份说明
    你是专业的[领域名称]智能助手，精通[核心技能1]、[核心技能2]、[核心技能3]。
    使用中文与用户交流，提供从[起始阶段]到[结束阶段]的全流程支持。
    
    # 🚦 策略说明  
    根据用户意图选择合适策略：
    [定义你的工作流程和策略]
    """
```

#### 2. 替换专业工具集
在 `main.py` 中的 `setup_agent()` 函数中替换工具集：

```python
toolkit = [
    # 替换为你的专业工具
    your_domain_tool_1,
    your_domain_tool_2,
    your_domain_tool_3,
    # 保留通用工具
    execute_command,
    file_operations,
    sketch_pad_operations,
]
```

#### 3. 开发专业工具
参考 `tools/` 目录下的现有工具，创建你的专业工具模块：

```python
@tool(name="your_domain_tool", description="专业工具描述")
def your_domain_tool(param1: str, param2: int) -> str:
    """你的专业工具实现"""
    pass
```

### 领域适配示例

#### 数据分析助手
- **工具集**: pandas操作、可视化生成、统计分析、模型训练
- **工作流**: 数据探索 → 清洗处理 → 分析建模 → 结果可视化

#### 代码开发助手  
- **工具集**: 代码生成、测试编写、文档生成、代码审查
- **工作流**: 需求分析 → 架构设计 → 代码实现 → 测试验证

#### 文档写作助手
- **工具集**: 内容研究、结构规划、文档生成、格式美化
- **工作流**: 主题确定 → 大纲设计 → 内容创作 → 审校发布

## 💡 使用指南（以CAD助手为例）

> 📢 **注意**: 以下是框架当前CAD建模实现的使用示例。通过修改Prompt和工具集，可以轻松适配其他专业领域。

### 基本对话

启动后，您可以直接与 CAD 助手对话：

```
>>> 帮我设计一个 DN100 PN16 的法兰
```

### 特殊命令

系统支持多种特殊命令来管理会话和数据：

#### 会话管理
- `/help` - 显示帮助信息
- `/history` - 查看当前会话历史
- `/full_history` - 查看完整保存历史
- `/clear` - 清空当前会话历史
- `/summary` - 显示当前会话摘要
- `/export <filename>` - 导出会话记录

#### SketchPad 管理
- `/pad` - 显示 SketchPad 内容
- `/pad_stats` - 显示统计信息
- `/pad_search <query>` - 搜索内容
- `/pad_store <key> <value>` - 存储内容
- `/pad_get <key>` - 获取内容
- `/pad_clear` - 清空 SketchPad

### CAD 建模工作流

#### 1. 需求细化
```
>>> 设计一个齿轮，18 齿，模数为 2
```

助手会自动细化需求，确定关键参数如：
- 齿数、模数、压力角
- 材料要求、精度等级
- 安装方式、配合要求

#### 2. 代码生成
基于细化的需求，自动生成 CADQuery 代码：
```python
import cadquery as cq

# 齿轮参数
teeth = 18
module = 2
# ... 更多参数和建模代码
```

#### 3. 文件组织
自动创建语义化文件夹结构：
```
./齿轮_18齿_模数2/
├── model.py          # CADQuery 脚本
├── 齿轮.step         # STEP 格式文件
├── 齿轮.stl          # STL 格式文件
└── multi_view_render.png  # 多视角渲染图
```

#### 4. 执行和验证
- 自动执行 Python 脚本
- 生成 STEP 和 STL 文件
- 创建多视角渲染图进行可视化验证

## 🏗️ 项目结构

```
SimpleAgent_General/
├── main.py                 # 主程序入口
├── pyproject.toml         # 项目配置
├── uv.lock               # 依赖锁定文件
├── agent/                # 智能体核心模块
│   └── BaseAgent.py      # 基础智能体类
├── config/               # 配置管理
│   ├── config.py         # 配置加载器
│   ├── provider.json     # API 配置文件
│   └── provider_template.json  # 配置模板
├── context/              # 上下文管理
│   ├── context.py        # 对话上下文管理
│   └── sketch_pad.py     # 智能存储系统
├── tools/                # 工具集合
│   ├── requirements_tools.py    # 需求细化工具
│   ├── code_tools.py           # 代码生成工具
│   ├── file_tools.py           # 文件操作工具
│   ├── command_tools.py        # 命令执行工具
│   ├── model_view_tools.py     # 3D 渲染工具
│   └── sketch_tools.py         # SketchPad 工具
└── sandbox/              # 工作沙盒
    └── 最简单法兰/         # 示例项目
        ├── model.py
        ├── simple_flange.step
        ├── simple_flange.stl
        └── multi_view_render.png
```

## 🔧 核心模块详解

### BaseAgent 类（框架核心）
通用智能体的核心类，提供：
- **LLM 接口管理**: 支持多种大语言模型的统一调用
- **工具调用框架**: 动态工具注册和智能调用机制  
- **对话流控制**: 流式输出和上下文管理
- **SketchPad 集成**: 智能数据存储和检索
- **错误处理**: 完善的异常捕获和恢复机制

### ConversationContext 类（上下文管理）
对话上下文管理器，提供：
- **单例模式**: 全局统一的上下文管理
- **历史记录**: 自动存储和检索对话历史
- **智能摘要**: AI驱动的长期记忆和摘要
- **会话元数据**: 丰富的会话统计和管理信息

### SketchPad 系统（智能存储）
通用智能存储系统，特点：
- **LRU 缓存**: 基于访问频率的智能内存管理
- **标签系统**: 支持多维度的内容分类和检索
- **AI 摘要**: 自动生成内容摘要，便于快速定位
- **持久化**: 数据持久化存储，支持会话恢复

### 当前CAD工具集（可替换）
1. **make_user_query_more_detailed**: 需求细化和标准化
2. **cad_query_code_generator**: 高质量 CAD 代码生成  
3. **file_operations**: 智能文件操作和管理
4. **execute_command**: 安全的命令执行环境
5. **render_multi_view_model**: 3D 模型多视角渲染
6. **sketch_pad_operations**: SketchPad 数据管理

> 🔧 **自定义提示**: 替换为你的专业领域工具，如数据分析、代码开发、文档写作等工具集

## 📋 依赖项说明

### 框架核心依赖
- **SimpleLLMFunc (0.2.8)**: LLM 接口和工具调用框架
- **Rich**: 美化控制台输出和交互界面

### 当前CAD实现相关（可选）
- **CADQuery (>=2.5.2)**: Python 参数化 CAD 建模库
- **cq-editor (>=0.5.0)**: CADQuery 可视化编辑器
- **cascadio (>=0.0.16)**: CAD 文件格式支持
- **trimesh (>=4.6.12)**: 3D 网格处理
- **pyrender**: 3D 渲染引擎
- **PyOpenGL**: OpenGL Python 绑定
- **numpy**: 数值计算支持
- **PIL/Pillow**: 图像处理

> 💡 **自定义提示**: 根据你的专业领域需求，替换或添加相应的专业库

## 🎮 示例用法

### 当前CAD建模实现示例

#### 基础 CAD 建模
```
>>> 设计一个 M8 的六角螺栓，长度 20mm
```

#### 复杂零件设计
```
>>> 创建一个减速器齿轮，输入轴齿数 20，输出轴齿数 60，模数 3
```

#### 标准件设计
```
>>> 设计一个 DN150 PN25 的对焊法兰，符合 HG/T20592 标准
```

### 其他领域适配示例

#### 数据分析助手
```
>>> 分析这个销售数据，找出季节性趋势和异常值
>>> 构建一个预测模型来预估下季度销量
```

#### 代码开发助手
```
>>> 帮我设计一个用户认证系统的API架构
>>> 为这个函数编写单元测试和文档
```

#### 文档写作助手
```
>>> 撰写一份关于AI在教育领域应用的研究报告
>>> 将这个技术文档改写为用户友好的使用指南
```

> 🚀 **扩展潜力**: 通过简单的配置修改，SimpleAgent可以成为任何专业领域的智能助手

## 🤝 贡献指南

欢迎贡献代码和建议！请遵循以下步骤：

1. Fork 项目仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持与反馈

如果您遇到问题或有建议，请：
1. 查看文档和示例
2. 搜索已有的 Issues
3. 创建新的 Issue 描述问题
4. 联系项目维护者

---

**SimpleAgent** - 一次开发，多域复用的通用智能体框架！

