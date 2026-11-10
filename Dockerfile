# Imagen base de Python (Debian slim: ligera) con pip incluido.
FROM python:3.11-slim

# PYTHONDONTWRITEBYTECODE: no genera .pyc en el sistema de archivos.
# PYTHONUNBUFFERED: los logs de uvicorn llegan inmediatamente a la consola.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Se copia primero solo requirements.txt para aprovechar la cache de Docker:
# mientras no cambie las dependencias, las capas siguientes no se reconstruyen.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Luego se copia el resto del código de la app.
COPY . .

EXPOSE 8000

# "fastapi[standard]" incluye uvicorn entre sus dependencias, así que basta con él
# para servir la aplicación: uvicorn lee la variable de entorno PORT si se define.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
