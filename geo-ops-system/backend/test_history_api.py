import requests
import json

# 测试历史API
try:
    r = requests.get('http://127.0.0.1:7007/api/scheduled-tasks/1/history?limit=10')
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Response type: {type(data)}")
    print(f"Keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
    if isinstance(data, dict) and 'items' in data:
        print(f"Items count: {len(data['items'])}")
        if data['items']:
            print(f"First item: {json.dumps(data['items'][0], indent=2, ensure_ascii=False)[:500]}")
        else:
            print("No items!")
    elif isinstance(data, list):
        print(f"List length: {len(data)}")
    else:
        print(f"Raw response: {str(data)[:500]}")
except Exception as e:
    print(f"Error: {e}")
