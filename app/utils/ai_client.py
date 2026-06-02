import os
import json
import re
import requests

# DeepSeek API 配置（通过环境变量读取）
API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")


def generate_cases(prompt: str, api_context: dict = None) -> list:
    """
    调用 DeepSeek API 生成接口测试用例

    Args:
        prompt: 用户提供的测试需求描述
        api_context: 接口上下文信息，包含 api_url, api_method, api_params 等

    Returns:
        生成的测试用例列表，每个用例包含 name, method, url, headers, body, assertions
    """
    if not API_KEY:
        raise ValueError("未配置 ANTHROPIC_AUTH_TOKEN（DeepSeek API Key）")

    # 构建完整的用户提示词
    api_info = api_context or {}
    api_url = api_info.get("api_url", "")
    api_method = api_info.get("api_method", "GET")
    api_params = api_info.get("api_params", {})

    user_prompt = f"""请根据以下接口信息生成测试用例：

【接口路径】{api_method} {api_url}
【接口参数】{json.dumps(api_params, ensure_ascii=False, indent=2) if api_params else "无"}

【用户需求】{prompt}

生成要求：
- 测试数据应使用真实数据，在 url、headers、body 中使用数据工厂占位符
- 数据工厂占位符格式：{{$函数名}}，在执行时自动生成真实数据
- 可用函数：
  · {{$uuid}} — 生成 UUID
  · {{$timestamp}} — 当前时间戳
  · {{$datetime}} — 当前日期时间
  · {{$random.email}} — 随机邮箱
  · {{$random.phone}} — 随机手机号
  · {{$random.name}} — 随机姓名
  · {{$random.address}} — 随机地址
  · {{$random.string(8)}} — 随机 8 位字符串
  · {{$random.number(1,100)}} — 1~100 随机数字

请严格按照 JSON 格式输出，不要包含任何解释文字。"""

    # 系统提示词 - 强制 JSON 输出
    system_prompt = """你是一个测试用例生成专家。根据用户提供的接口信息和需求，生成一组接口测试用例。
输出格式必须是合法的 JSON，结构如下：
{
  "cases": [
    {
      "name": "用例名称",
      "method": "GET/POST/PUT/DELETE",
      "url": "/path",
      "headers": {"Content-Type": "application/json"},
      "body": {},
      "assertions": [{"type": "status_code", "expected": 200}]
    }
  ]
}
要求：
- 至少包含正常、异常、边界值用例
- assertions 至少包含状态码断言
- 在 body / url / headers 中使用数据工厂占位符生成真实测试数据，例如：
  · 注册/登录接口用 {{$random.email}} 和 {{$random.phone}}
  · 需要唯一标识的地方用 {{$uuid}}
  · 分页参数用 {{$random.number(1,10)}}
  · 名称字段用 {{$random.name}}
  · 地址字段用 {{$random.address}}
- 不要输出任何解释，只输出 JSON"""

    # 调用 DeepSeek API（Anthropic 兼容接口）
    url = f"{BASE_URL}/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "max_tokens": 4000,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    response = requests.post(url, json=payload, headers=headers, timeout=120)
    response.raise_for_status()

    result = response.json()

    # 解析响应（Anthropic 消息格式）
    content = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")

    if not content:
        raise ValueError("API 返回内容为空")

    # 尝试从响应中提取并解析 JSON
    content = content.strip()

    # 1) 先尝试直接解析
    parsed = None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2) 处理 markdown 代码块 ```json ... ```
    if parsed is None:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # 3) 找到第一个 { 和最后一个 } 提取 JSON
    if parsed is None:
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start >= 0 and json_end > json_start:
            try:
                parsed = json.loads(content[json_start:json_end + 1])
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"无法解析 API 返回为 JSON (位置 {e.pos}): "
                    f"{content[json_start:json_end + 1][:300]}"
                )
        else:
            raise ValueError(f"返回内容中未找到 JSON: {content[:200]}")

    cases = parsed.get("cases", [])
    if not cases:
        raise ValueError("API 返回的用例列表为空")

    # 规范化和补全用例字段
    for case in cases:
        case.setdefault("method", "GET")
        case.setdefault("url", "")
        case.setdefault("headers", {"Content-Type": "application/json"})
        case.setdefault("body", None)
        case.setdefault("assertions", [{"type": "status_code", "expected": 200}])

    return cases
