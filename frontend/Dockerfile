FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
