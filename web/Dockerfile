# codebase-rag dashboard frontend (v2 PRD, T11). Multi-stage: build with
# the full toolchain, run from Next.js's self-contained `standalone` output
# (next.config.ts) so the final image doesn't carry `node_modules`.
FROM node:22-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked in at build time, not just runtime - Next.js inlines every
# `NEXT_PUBLIC_*` reference into the compiled output (lib/config.ts), so
# setting this only as a `docker compose environment:` entry would be a
# no-op. `api` is this stack's Docker Compose service name, resolved by
# Docker's internal DNS - not the NAS's LAN address, since the api service
# itself is never published to the LAN (see next.config.ts's rewrite).
ENV NEXT_PUBLIC_API_URL=http://api:8000
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# Kept at runtime too - next.config.ts's rewrite() reads it live (it's a
# plain Node config file, not part of the compiled app), so this needs to
# still be set on the running container, not just during the build above.
ENV NEXT_PUBLIC_API_URL=http://api:8000

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
