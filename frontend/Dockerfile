# Local development only. Do not expose the Vite dev server to the Internet.
FROM node:24-bookworm-slim
WORKDIR /app

# npm install creates the first lockfile; subsequent locked builds use npm ci.
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN chown -R node:node /app
USER node
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
