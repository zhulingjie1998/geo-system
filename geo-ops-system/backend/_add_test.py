import sys

with open('app.py', 'rb') as f:
    data = f.read()

# Add test endpoint
test_endpoint = b'\n\n@app.get("/api/test-debug")\ndef api_test_debug():\n    return jsonify({"msg": "TEST-WORKS-" + str(len(_perms_registry.PAGE_REGISTRY)), "scopes": list(_perms_registry.VALID_DATA_SCOPES)})\n\n'

marker = b'@app.get("/api/permissions/registry")'
if marker in data:
    data = data.replace(marker, test_endpoint + marker, 1)
    with open('app.py', 'wb') as f:
        f.write(data)
    print('Test endpoint added')
else:
    print('Marker not found')
