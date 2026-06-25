FROM node:20-alpine

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
EXPOSE 3000
# Dev server for the demo; use `npm run build && npm start` for production.
CMD ["npm", "run", "dev"]
