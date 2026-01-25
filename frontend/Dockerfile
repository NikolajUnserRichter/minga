FROM node:20-alpine

WORKDIR /app

# Package files
COPY package*.json ./

# Dependencies installieren
RUN npm install

# Quellcode
COPY . .

# Port
EXPOSE 3000

# Entwicklungsserver
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
