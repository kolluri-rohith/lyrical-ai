# ---- Build the static bundle ----
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# ---- Serve with Nginx ----
# The server config is not baked in: docker-compose mounts nginx/nginx.conf to
# /etc/nginx/templates/default.conf.template, which the image renders on start.
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
