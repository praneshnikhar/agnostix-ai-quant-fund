# AI Quant Fund — Web image (multi-stage, non-root)
FROM node:20-alpine AS deps
WORKDIR /workspace/apps/web
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm ci || npm install

FROM node:20-alpine AS builder
WORKDIR /workspace
COPY --from=deps /workspace/apps/web/node_modules ./apps/web/node_modules
COPY packages ./packages
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /workspace/apps/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /workspace/packages /workspace/packages
COPY --from=builder --chown=node:node /workspace/apps/web/.next ./.next
COPY --from=builder /workspace/apps/web/public ./public
COPY --from=builder /workspace/apps/web/package.json ./package.json
COPY --from=builder /workspace/apps/web/next.config.mjs ./next.config.mjs

USER node
EXPOSE 3000
CMD ["npx", "next", "start"]