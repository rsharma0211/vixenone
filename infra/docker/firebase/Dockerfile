FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    netcat-openbsd \
    bash \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g firebase-tools@13.29.1

WORKDIR /firebase

COPY firebase.json /firebase/
COPY infra/docker/firebase/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 4000 9099 4400

ENTRYPOINT ["/entrypoint.sh"]
