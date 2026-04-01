# Stage 1: Build the Vite React App
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Install dependencies (leverage cache)
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install

# Copy source code and build
COPY dashboard/ ./
# Add environment variable mapping for production build
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:alpine

# Copy custom Nginx configuration to support client-side routing
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from previous stage
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port (Cloud Run expects 8080 by default, Nginx listens on 80 by default, 
# so we will configure nginx.conf to listen on 8080)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
