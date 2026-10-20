# syntax=docker/dockerfile:1
#
# Web image. Two stages:
#   build:   Node installs the dependencies and builds the static files (dist/)
#   runtime: unprivileged nginx serves dist/ and proxies /api to the api service

# ---------------------------------------------------------------------------- build
FROM node:24.22.0-alpine AS build

WORKDIR /web

# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------------------------------------------------------------------------- runtime
FROM nginxinc/nginx-unprivileged:1.29.8-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
