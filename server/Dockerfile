FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates bubblewrap \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex@latest \
    && mkdir -p /app /sandbox /codex-home \
    && chown -R node:node /app /sandbox /codex-home

WORKDIR /app
COPY --chown=node:node server.mjs /app/server.mjs
USER node

ENV PORT=8092 CODEX_MODEL=gpt-5.6-terra
EXPOSE 8092
CMD ["node", "/app/server.mjs"]
