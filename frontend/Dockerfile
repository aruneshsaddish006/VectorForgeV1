# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Vector-Forge frontend (Next.js 16 / React 19 / Tailwind v4)
#
# Multi-stage build producing a minimal, non-root production image using
# Next.js "standalone" output. Final image is ~150-200MB vs ~1GB+ for a
# naive single-stage build.
#
#   IMPORTANT: NEXT_PUBLIC_* values are inlined into the client bundle at
#   BUILD time, not runtime. They must be passed as --build-arg (see below),
#   NOT injected as container env vars at deploy time.
# ---------------------------------------------------------------------------

ARG NODE_VERSION=22-alpine

# ---- 1. deps: install node_modules (cached unless package.json changes) ----
FROM node:${NODE_VERSION} AS deps
WORKDIR /app

# libc6-compat helps some native deps run on Alpine
RUN apk add --no-cache libc6-compat

# No lockfile is committed; copy whatever package manifests exist and let
# npm resolve. Using `npm install` (not `ci`) because there is no package-lock.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# ---- 2. builder: compile the Next.js app ----------------------------------
FROM node:${NODE_VERSION} AS builder
WORKDIR /app

# Public (client-visible) backend URLs. These are baked into the JS bundle.
# Override per environment at build time:
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com ...
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_CONV_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_CONV_API_URL=${NEXT_PUBLIC_CONV_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ---- 3. runner: minimal runtime image -------------------------------------
FROM node:${NODE_VERSION} AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run as an unprivileged user
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# Static assets and the standalone server bundle.
# `standalone` already contains a trimmed node_modules + server.js.
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# Lightweight container healthcheck (ALB/ECS will hit "/" as well)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+ (process.env.PORT||3000) +'/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# server.js is emitted by Next.js standalone output
CMD ["node", "server.js"]
