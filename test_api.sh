#!/bin/bash

# SimpleAgent API 测试脚本
# 使用curl命令测试各个API端点

BASE_URL="http://localhost:8000"

echo "🧪 SimpleAgent API 测试脚本"
echo "==============================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试函数
test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local data=$4
    local expected_status=$5
    
    echo -e "${BLUE}测试: $name${NC}"
    echo "URL: $method $url"
    
    if [ -n "$data" ]; then
        echo "Data: $data"
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X $method \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url")
    else
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X $method "$url")
    fi
    
    # 提取HTTP状态码
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo "Response Status: $http_status"
    echo "Response Body:"
    echo "$response_body" | python3 -m json.tool 2>/dev/null || echo "$response_body"
    
    if [ "$http_status" -eq "$expected_status" ]; then
        echo -e "${GREEN}✅ 测试通过${NC}"
    else
        echo -e "${RED}❌ 测试失败 (期望状态码: $expected_status, 实际: $http_status)${NC}"
    fi
    
    echo ""
    echo "----------------------------------------"
    echo ""
}

echo "开始测试 SimpleAgent API..."
echo ""

# 1. 测试服务器根路径
test_endpoint "服务器信息" "GET" "$BASE_URL/" "" 200

# 2. 测试健康检查
test_endpoint "健康检查" "GET" "$BASE_URL/health" "" 200

# 3. 测试模型列表
test_endpoint "模型列表" "GET" "$BASE_URL/v1/models" "" 200

# 4. 测试聊天完成API (非流式)
chat_data='{
  "model": "simple-agent-v1",
  "messages": [
    {
      "role": "user",
      "content": "你好，请简单介绍一下你自己"
    }
  ],
  "stream": false
}'

test_endpoint "聊天完成 (非流式)" "POST" "$BASE_URL/v1/chat/completions" "$chat_data" 200

# 5. 测试聊天完成API (流式) - 只显示前几行
echo -e "${BLUE}测试: 聊天完成 (流式)${NC}"
echo "URL: POST $BASE_URL/v1/chat/completions"

stream_data='{
  "model": "simple-agent-v1",
  "messages": [
    {
      "role": "user",
      "content": "请说一个简短的问候"
    }
  ],
  "stream": true
}'

echo "Data: $stream_data"
echo "Response (前10行):"
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$stream_data" \
    "$BASE_URL/v1/chat/completions" | head -10

echo ""
echo -e "${GREEN}✅ 流式响应测试完成 (仅显示前10行)${NC}"
echo ""
echo "----------------------------------------"
echo ""

# 6. 测试错误处理 - 空消息
error_data='{
  "model": "simple-agent-v1",
  "messages": []
}'

test_endpoint "错误处理 (空消息)" "POST" "$BASE_URL/v1/chat/completions" "$error_data" 400

# 7. 测试404错误
test_endpoint "404错误" "GET" "$BASE_URL/nonexistent" "" 404

echo -e "${YELLOW}🎉 API测试完成！${NC}"
echo ""
echo "如果所有测试都通过，说明你的SimpleAgent服务器运行正常。"
echo "如果有测试失败，请检查服务器是否正在运行在 $BASE_URL"
