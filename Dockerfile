FROM node:22-bookworm-slim AS node-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
COPY tests ./tests
RUN npm run build

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 git curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=node-builder /app/node_modules ./node_modules
COPY --from=node-builder /app/dist ./dist
COPY package.json ./
COPY . .
EXPOSE 8000
ENTRYPOINT ["python", "run.py", "--no-browser", "--port", "8000"]
