# SimpleAgent WebSocket API 文档

本文档详细说明了如何通过 WebSocket 与 SimpleAgent API 进行交互，以实现流式聊天完成功能。

## 端点 URL

```
ws://<your-server-address>:<port>/v1/chat/completions/ws
```

-   **协议**: `ws://` (或在 TLS/SSL 环境下为 `wss://`)
-   **默认地址**: `ws://localhost:8000/v1/chat/completions/ws`

## 通信流程

客户端与服务器之间的通信遵循以下步骤：

1.  客户端通过标准 WebSocket 握手连接到上述端点。
2.  连接成功后，客户端发送一个 JSON 格式的请求对象。
3.  服务器以流式方式发回一系列 JSON 格式的响应对象。
4.  服务器在完成响应后，会发送一个最终的结束消息。
5.  连接可以保持打开状态，以接收后续请求，或者由客户端或服务器关闭。

---

## 请求 (Client -> Server)

客户端应通过 WebSocket 连接发送一个 JSON 对象。此对象的结构与 `POST /v1/chat/completions` HTTP 端点使用的 `ChatCompletionRequest` 模型完全相同。

### 请求 Schema

| 字段 | 类型 | 必需 | 描述 |
| :--- | :--- | :--- | :--- |
| `model` | string | 是 | 要使用的模型 ID，例如 `"simple-agent-v1"`。 |
| `messages` | array | 是 | 代表对话历史的消息对象列表。 |
| `stream` | boolean | 否 | 虽然在 WebSocket 上下文中流式传输是隐含的，但此字段可能会被包含。
| `temperature`| number | 否 | 控制随机性的值，介于 0 和 2 之间。 |
| `max_tokens` | integer | 否 | 生成响应的最大令牌数。 |

### `messages` 对象结构

| 字段 | 类型 | 必需 | 描述 |
| :--- | :--- | :--- | :--- |
| `role` | string | 是 | 消息发送者的角色，如 `"user"`, `"assistant"`, 或 `"system"`。 |
| `content` | string \| array | 是 | 消息的具体内容。可以是纯文本字符串，或包含多模态内容的数组。 |

### 多模态内容支持

当 `content` 为数组时，每个元素为一个内容对象，支持以下类型：

**文本内容对象：**
| 字段 | 类型 | 必需 | 描述 |
| :--- | :--- | :--- | :--- |
| `type` | string | 是 | 内容类型，值为 `"text"`。 |
| `text` | string | 是 | 文本内容。 |

**图像内容对象：**
| 字段 | 类型 | 必需 | 描述 |
| :--- | :--- | :--- | :--- |
| `type` | string | 是 | 内容类型，值为 `"image_url"`。 |
| `image_url` | object | 是 | 图像信息对象。 |

**图像信息对象结构：**
| 字段 | 类型 | 必需 | 描述 |
| :--- | :--- | :--- | :--- |
| `url` | string | 是 | 图像的 URL，支持 `http://`、`https://` 或 `data:` 协议的 base64 编码图像。 |
| `detail` | string | 否 | 图像处理细节级别，可选值：`"low"`, `"high"`, `"auto"`。默认为 `"auto"`。 |

### 请求示例

**纯文本请求示例：**
```json
{
  "model": "simple-agent-v1",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello, who are you?"
    }
  ]
}
```

**多模态请求示例：**
```json
{
  "model": "simple-agent-v1",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant that can analyze images."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "请描述这张图片中的内容"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg",
            "detail": "high"
          }
        }
      ]
    }
  ]
}
```

**Base64 编码图像示例：**
```json
{
  "model": "simple-agent-v1",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "分析这张图片"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAhEAACAQMDBQAAAAAAAAAAAAABAgMABAUGIWGRkqGx4//EABUBAQEAAAAAAAAAAAAAAAAAAAMF/8QAGhEAAgIDAAAAAAAAAAAAAAAAAAECEgMRkf/aAAwDAQACEQMRAD8AltJagyeH0AthI5xdrLcNM91BF5pX2HaH9bcfaSXWGaRmknyJckliyjqTzSlT54b6bk+h0R/HuBZODdroXUuBGcY="
          }
        }
      ]
    }
  ]
}
```

---

## 响应 (Server -> Client)

为了确保消息传递的顺序和可靠性，服务器发送的每个响应都封装在一个标准的数据包结构中。客户端收到的每个 WebSocket 消息都是一个包含以下字段的 JSON 对象：

| 字段 | 类型 | 描述 |
| :--- | :--- | :--- |
| `sequence` | integer | 数据包的序列号，从 0 开始为每个请求递增。 |
| `payload` | object | 实际的数据负载，其内容是下面描述的某一种响应类型。 |

### 1. 内容块 (Stream Chunks)

在处理过程中，服务器会发送多个数据包，其 `payload` 符合 `ChatCompletionChunk` 模型。

**数据包示例:**

```json
{
  "sequence": 0,
  "payload": {
    "id": "chatcmpl-xxxxxxxx",
    "object": "chat.completion.chunk",
    "created": 1677652288,
    "model": "simple-agent-v1",
    "choices": 
      {
        "index": 0,
        "delta": {
          "content": "I am an AI assistant."
        },
        "finish_reason": null
      }
    ]
  }
}
```
-   `payload.delta.content` 包含了响应内容的片段。客户端需要将这些片段拼接起来以获得完整响应。

### 2. 结束消息

当流结束时，服务器会发送一个最终的数据包，其 `payload` 中 `finish_reason` 为 `"stop"`。这标志着一次完整的响应已经发送完毕。

**结束数据包示例:**

```json
{
  "sequence": 42,
  "payload": {
    "id": "chatcmpl-xxxxxxxx",
    "choices": [
      {
        "finish_reason": "stop"
      }
    ]
  }
}
```

### 3. 错误响应

如果在处理过程中发生错误（例如，请求格式无效或服务器内部错误），服务器会发送一个 `ErrorResponse` 对象。**请注意，错误响应目前未封装在标准数据包结构中。**

**错误响应 Schema 示例:**

```json
{
  "error": {
    "message": "Invalid request format: ...",
    "type": "invalid_request",
    "param": null,
    "code": null
  }
}
```

---

## 客户端实现注意事项

-   **JSON 解析**: 客户端需要能够解析从 WebSocket 接收到的每一个 JSON 消息，并处理封装的数据包结构。
-   **序列号处理**: 客户端应验证并根据 `sequence` 字段对消息进行排序，以确保消息的正确顺序。如果收到乱序的包，可以先缓存它们。
-   **状态管理**: 客户端应检查 `payload.choices[0].finish_reason` 是否为 `"stop"`，以确定何时完成一次完整的对话交换。
-   **错误处理**: 实现对 `ErrorResponse` 格式的错误消息的处理逻辑。
-   **连接生命周期**: 客户端负责在不再需要时关闭 WebSocket 连接。
-   **多模态内容处理**: 
    - 当发送包含图像的消息时，确保图像 URL 可访问或 base64 编码格式正确。
    - 支持动态构建 `content` 数组，根据用户输入包含文本和图像内容。
    - 处理大型图像时，考虑压缩或调整 `detail` 参数以优化性能。
    - 验证图像格式支持（通常支持 JPEG、PNG、GIF、WebP 等常见格式）。
