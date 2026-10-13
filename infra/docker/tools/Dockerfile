FROM node:24.21.0-bookworm-slim AS node

FROM google/cloud-sdk:588.0.0-slim

COPY --from=node /usr/local /usr/local

RUN npm install -g firebase-tools@15.33.0

WORKDIR /workspace
