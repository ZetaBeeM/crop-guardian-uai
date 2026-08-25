# --- Etapa 1: build del frontend (React + Vite) ---
FROM node:22-slim AS frontend
WORKDIR /app

# Antes que el codigo, para que la capa se reutilice si no cambia el lock.
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig*.json ./
COPY public ./public
COPY src ./src
RUN npm run build


# --- Etapa 2: backend Flask, que ademas sirve el frontend construido ---
FROM python:3.12-slim

# Antes de los COPY, para poder usar --chown: COPY conserva los permisos del
# host y varios .py estan en 600, ilegibles para appuser si quedan de root.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /backend

# Sin esto los print quedan en el buffer y no llegan a `docker logs`.
ENV PYTHONUNBUFFERED=1

COPY --chown=appuser:appuser src/backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser src/backend/ .

# app.py lo sirve desde "/" con static_url_path="".
COPY --from=frontend --chown=appuser:appuser /app/dist ./static

USER appuser

EXPOSE 5000

# 180s porque /api/analizar-cultivo encadena dos llamadas a Foundry y una
# escritura en Cosmos. gthread porque la carga es espera de red, no CPU.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", "--threads", "8", \
     "--timeout", "180", "app:app"]
