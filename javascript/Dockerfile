# Build from this directory (javascript/):
#   docker build -t dark-matter-js .
#
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY src ./src
COPY views ./views
ENV NODE_ENV=production
ENV PORT=5000
EXPOSE 5000
CMD ["node", "src/server.js"]
