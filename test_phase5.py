"""Test Phase 5: AI Generate + Import"""
import json
from app import create_app

app = create_app()

with app.test_client() as c:
    # Login
    resp = c.post("/api/auth/login", json={"username": "testuser", "password": "123456"})
    token = resp.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get project
    resp = c.get("/api/project", headers=headers)
    projects = resp.get_json()["data"]
    if not projects:
        print("No project found, creating one...")
        resp = c.post("/api/project", json={"name": "AI测试项目"}, headers=headers)
        project_id = resp.get_json()["data"]["id"]
    else:
        project_id = projects[0]["id"]
    print(f"Using project: {project_id}")

    # === AI GENERATE ===
    print("\n=== AI Generate Test Cases ===")

    generate_payload = {
        "project_id": project_id,
        "api_url": "/api/user/register",
        "api_method": "POST",
        "api_params": {
            "username": "string (required, max 50 chars)",
            "password": "string (required, min 6 chars)",
            "email": "string (optional)",
            "role": "string (optional, default: user)"
        },
        "prompt": "为用户注册接口生成测试用例，需要包含正常注册、用户名已存在、密码太短、缺少必填字段等场景",
        "case_count": 8,
    }

    print("Calling DeepSeek API... (may take 10-30 seconds)")
    resp = c.post("/api/ai/generate/api-case", json=generate_payload, headers=headers)
    print(f"POST /api/ai/generate/api-case: {resp.status_code}")

    data = resp.get_json()
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if data["code"] == 200:
        record_id = data["data"]["record_id"]
        cases = data["data"]["cases"]
        print(f"\nGenerated {len(cases)} cases:")

        # Show generated case names
        for i, case in enumerate(cases):
            print(f"  [{i}] {case.get('method', 'GET')} {case.get('url', '')} - {case.get('name', 'unnamed')}")

        # === IMPORT ===
        print("\n=== Import Cases ===")

        # Import first 3 cases
        import_payload = {
            "record_id": record_id,
            "case_ids_to_import": [0, 1, 2],
        }
        resp = c.post("/api/ai/import", json=import_payload, headers=headers)
        print(f"POST /api/ai/import: {resp.status_code}")
        import_data = resp.get_json()
        print(json.dumps(import_data, ensure_ascii=False, indent=2))

        # === QUERY RECORDS ===
        print("\n=== Query AI Records ===")
        resp = c.get(f"/api/ai/record?project_id={project_id}", headers=headers)
        print(f"GET /api/ai/record?project_id={project_id}: {resp.status_code}")
        data = resp.get_json()
        print(f"  Records count: {len(data['data'])}")
        for r in data["data"]:
            print(f"  - Record {r['id']}: status={r['status']}, cases={r['case_count']}, prompt={r['prompt'][:50]}...")

        # Get record detail
        resp = c.get(f"/api/ai/record/{record_id}", headers=headers)
        print(f"\nGET /api/ai/record/{record_id}: {resp.status_code}")
        print(f"  Status: {resp.get_json()['data']['status']}")
        print(f"  Cases: {json.dumps(resp.get_json()['data']['generated_cases'], ensure_ascii=False, indent=2)[:300]}...")

        # Verify imported cases are in the project
        resp = c.get(f"/api/case?project_id={project_id}", headers=headers)
        print(f"\nVerify: project now has {len(resp.get_json()['data'])} cases")

    # === ERROR CASES ===
    print("\n=== Error Cases ===")
    resp = c.post("/api/ai/generate/api-case", json={}, headers=headers)
    print(f"Empty request: {resp.status_code} - {resp.get_json()['msg']}")

    resp = c.post("/api/ai/import", json={"record_id": 9999, "case_ids_to_import": [0]}, headers=headers)
    print(f"Import invalid record: {resp.status_code} - {resp.get_json()['msg']}")

    resp = c.get("/api/ai/record/9999", headers=headers)
    print(f"Get invalid record: {resp.status_code} - {resp.get_json()['msg']}")

    print("\n=== All Phase 5 tests completed ===")
