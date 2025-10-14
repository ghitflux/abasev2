FROM node:20-alpine

WORKDIR /app

COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
RUN npm install -g pnpm@8.15.0
RUN pnpm install --frozen-lockfile || pnpm install

COPY apps/web ./apps/web
COPY packages ./packages

WORKDIR /app/apps/web

CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]
