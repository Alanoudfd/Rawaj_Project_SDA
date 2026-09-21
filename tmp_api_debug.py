from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
for path in ['/health', '/api/restaurants', '/api/restaurants/2/context']:
    try:
        r = client.get(path)
        print('PATH', path, 'STATUS', r.status_code)
        print(r.text[:500])
    except Exception:
        import traceback; traceback.print_exc()
