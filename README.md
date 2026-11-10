# How to run it

## Desarrollo (local)
```bash
fastapi dev app/main.py
```

## Producción (Docker)

Construir la imagen:
```bash
docker build -t financial-management-app .
```

Correr el contenedor (pasando la configuración por variables de entorno, p. ej. el GEMINI_API_KEY):
```bash
docker run -p 8000:8000 --env-file .env financial-management-app
```

La API queda disponible en `http://localhost:8000`. Para cambiar el puerto del host:
```bash
docker run -p 8080:8000 financial-management-app
```
