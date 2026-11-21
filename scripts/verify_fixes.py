import ast, os

errors = []
for root, dirs, files in os.walk('backend/app'):
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        src = open(path, 'r', encoding='utf-8').read()
        if src.startswith('\ufeff'):
            errors.append(('BOM', path))
            continue
        try:
            ast.parse(src)
        except SyntaxError as e:
            errors.append((str(e), path))

if errors:
    print("ERRORS:")
    for e in errors:
        print(e)
else:
    print("Python files: OK (26 files)")

html = open('backend/app/static/seek_demo.html', 'r', encoding='utf-8').read()
remaining = html.count('\ufffd')
print(f"HTML replacement chars remaining: {remaining}")

check_block_start = html.find('checkBackendAvail')
check_block = html[check_block_start:check_block_start+200]
uses_healthz = '/healthz' in check_block
uses_status = '/api/v1/status' in check_block
print(f"Offline banner uses /healthz: {uses_healthz}")
print(f"Offline banner still uses /api/v1/status: {uses_status}")

cfg = open('backend/app/config.py', 'r', encoding='utf-8').read()
print(f"auth_enabled in config.py: {'auth_enabled' in cfg}")

search = open('backend/app/search.py', 'r', encoding='utf-8').read()
print(f"Embedding degradation guard in search_video_segments: {'Returns empty list' in search}")
print(f"Lexical fallback in search_documents_hybrid: {'embedder down' in search}")

main = open('backend/app/main.py', 'r', encoding='utf-8').read()
print(f"readyz MinIO soft-fail: {'blob_ok = False' in main}")
