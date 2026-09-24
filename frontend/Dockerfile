FROM node:22-alpine AS build
ENV NODE_OPTIONS=--openssl-legacy-provider
WORKDIR /app
RUN corepack enable
COPY package.json ./package.json
COPY craco.config.js ./craco.config.js
COPY tailwind.config.js postcss.config.js ./
COPY public ./public
COPY src ./src
RUN yarn install --non-interactive
RUN yarn build

FROM nginx:stable-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
