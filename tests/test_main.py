from fastapi.testclient import TestClient

from app.main import app

# Creamos el cliente de pruebas basado en nuestra aplicación de FastAPI
client = TestClient(app)

def test_read_home():
    # La raíz ya no responde un JSON: lleva al Resumen (ver app/main.py).
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307

    assert response.headers["location"] == "/resumen"
