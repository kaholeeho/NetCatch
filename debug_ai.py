"""Debug AI client - see raw response from DeepSeek"""
import os
import json
import requests

API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")

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
- 不要输出任何解释，只输出 JSON"""

user_prompt = """请根据以下接口信息生成测试用例：

【接口路径】POST /api/user/register
【接口参数】{
  "username": "string (required, max 50 chars)",
  "password": "string (required, min 6 chars)",
  "email": "string (optional)",
  "role": "string (optional, default: user)"
}

【用户需求】为用户注册接口生成测试用例，需要包含正常注册、用户名已存在、密码太短、缺少必填字段等场景

请严格按照 JSON 格式输出，不要包含任何解释文字。"""

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

print(f"Calling: {url}")
print(f"Using API Key: {API_KEY[:8]}...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")

    result = response.json()
    print(f"\nFull response keys: {result.keys()}")
    print(f"Content: {result.get('content', [])}")
    print(f"\n---Raw content blocks---")
    for block in result.get("content", []):
        print(f"Type: {block.get('type')}")
        text = block.get("text", "")
        print(f"Text (first 500 chars):")
        print(text[:500])
        print(f"\n---Try to parse JSON---")
        # Try to find JSON in the text
        if "```" in text:
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                print("Found JSON in code block")
            else:
                json_str = text.strip()
        else:
            json_start = text.find("{")
            json_end = text.rfind("}")
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end + 1]
                print(f"Extracted JSON from position {json_start} to {json_end}")
            else:
                json_str = text

        try:
            parsed = json.loads(json_str)
            print(f"JSON parsed OK! {len(parsed.get('cases', []))} cases")
            for c in parsed.get("cases", []):
                print(f"  - {c.get('name', 'unnamed')}")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Problematic text (around error):")
            error_pos = e.pos
            print(f"...{json_str[max(0,error_pos-50):error_pos+50]}...")

except Exception as e:
    print(f"Error: {e}")
