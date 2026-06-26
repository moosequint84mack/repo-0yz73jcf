# Crypto-screener frontend: build the Vite SPA, serve it with nginx
# and reverse-proxy /api (REST + WebSocket) to the backend container.
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Landing page at site root, the SPA under /screener/.
COPY landing /usr/share/nginx/html
COPY --from=build /app/dist /usr/share/nginx/html/screener
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
