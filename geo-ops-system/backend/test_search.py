"""测试查词功能 - 直接测试适配器"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import time

# 直接导入并测试
print("=== Testing overseas_search_adapter ===")

from overseas_search_adapter import (
    KA_BASE_URL,
    PLATFORM_KA_MAP,
    _ka_post,
    submit_ka_tasks,
    query_ka_detail,
    poll_ka_until_complete,
    run_query,
)

print(f"\n1. KA_BASE_URL: {KA_BASE_URL}")
print(f"2. PLATFORM_KA_MAP: {PLATFORM_KA_MAP}")

# 测试3: 单条提交
print("\n=== 3. Test Single Submit (_ka_post) ===")
try:
    result = _ka_post("/firecrawl/kaTaskSubmit", {
        "keyword": "led light",
        "platform": "chatGpt",
        "language": "en"
    })
    print(f"Submit result: {json.dumps(result, ensure_ascii=False)}")
    task_id = result.get("localTaskId")
    if task_id:
        print(f"Got localTaskId: {task_id}")

        # 测试4: 轮询结果
        print("\n=== 4. Test Poll (poll_ka_until_complete) ===")
        results = poll_ka_until_complete([task_id], interval=10, max_wait=120)
        if results:
            final = results[0]
            print(f"Final status: {final.get('status')}")
            print(f"Error: {final.get('errorMessage')}")
            if final.get("result"):
                text = final["result"].get("text", "")[:200]
                print(f"Answer text (first 200 chars): {text}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# 测试5: run_query 完整流程
print("\n=== 5. Test run_query (full flow) ===")
try:
    result = run_query("ChatGPT", "chatGpt", "led light", brand="test")
    print(f"Success: {result.get('success')}")
    print(f"Answer (first 200): {result.get('answer_text', '')[:200]}")
    print(f"Error: {result.get('error_message', '')[:100]}")
    print(f"Duration: {result.get('duration')}s")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# 测试6: 批量提交
print("\n=== 6. Test Batch Submit ===")
try:
    batch_result = submit_ka_tasks([
        {"keyword": "led strip", "platform": "ChatGPT"},
        {"keyword": "led bulb", "platform": "Google AIO"}
    ])
    print(f"Batch submitted: {len(batch_result)} tasks")
    for r in batch_result:
        print(f"  - id={r.get('localTaskId')} keyword={r.get('keyword')} status={r.get('status')}")
except Exception as e:
    print(f"Batch ERROR: {e}")

print("\n=== ALL TESTS COMPLETE ===")
