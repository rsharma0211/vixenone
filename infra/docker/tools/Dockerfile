FROM node:20.18.0-bookworm-slim AS node

FROM google/cloud-sdk:588.0.0-slim

COPY --from=node /usr/local /usr/local

RUN npm install -g firebase-tools@13.29.1

WORKDIR /workspace
