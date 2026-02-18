# Pin to specific versions for reproducible builds
FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
