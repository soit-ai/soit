FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Left empty, the app calls the API at the relative /api/v1, which the
# runtime image proxies; the image then works under any hostname.
ARG VITE_BASE_URL
ENV VITE_BASE_URL=$VITE_BASE_URL
RUN npm run build

# The build is a static single-page app: no Node and no node_modules at run
# time. Caddy serves it and proxies the API on the same origin (Caddyfile).
FROM caddy:2.8-alpine AS runtime

RUN addgroup -S -g 10001 soit \
    && adduser -S -D -H -u 10001 -G soit soit \
    && mkdir -p /data /config \
    && chown -R soit:soit /data /config
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/build/client /srv

ENV XDG_DATA_HOME=/data \
    XDG_CONFIG_HOME=/config
EXPOSE 5000
USER soit
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
