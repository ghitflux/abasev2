FROM node:22-alpine

ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:$PATH"

WORKDIR /workspace

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

COPY package.json pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY packages/tsconfig/package.json packages/tsconfig/package.json
COPY packages/eslint-config/package.json packages/eslint-config/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json

RUN pnpm install --ignore-scripts

CMD ["pnpm", "--filter", "@abase/web", "dev", "--hostname", "0.0.0.0", "--port", "3000"]
