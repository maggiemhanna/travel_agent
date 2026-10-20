# syntax=docker/dockerfile:1
# Stage 1: Reproducible build from package-lock.json
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_FLIGHTS_SEARCH_API_URL=""
ARG VITE_CONVERSATIONAL_API_URL=""
ENV VITE_FLIGHTS_SEARCH_API_URL=${VITE_FLIGHTS_SEARCH_API_URL}
ENV VITE_CONVERSATIONAL_API_URL=${VITE_CONVERSATIONAL_API_URL}

RUN npm run build

# Stage 2: Production Nginx server with runtime env-config injection
FROM nginx:1.27-alpine

ENV PORT=8080

# Copy Nginx template (automatically processed by /docker-entrypoint.d/20-envsubst-on-templates.sh)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built static assets
COPY --from=build /app/dist /usr/share/nginx/html

# Generate /usr/share/nginx/html/env-config.js at container startup from Cloud Run env vars
RUN printf '#!/bin/sh\nset -e\ncat <<EOF > /usr/share/nginx/html/env-config.js\nwindow.__ENV__ = {\n  VITE_FLIGHTS_SEARCH_API_URL: "${VITE_FLIGHTS_SEARCH_API_URL:-}",\n  VITE_CONVERSATIONAL_API_URL: "${VITE_CONVERSATIONAL_API_URL:-}"\n};\nEOF\n' > /docker-entrypoint.d/40-generate-env-config.sh && \
    chmod +x /docker-entrypoint.d/40-generate-env-config.sh

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
