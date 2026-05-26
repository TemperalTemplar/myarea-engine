client_max_body_size 10M;

# ── Static files served directly by Nginx ──────────────────
location /static/ {
    alias /app/static/;
    expires 7d;
    add_header Cache-Control "public, immutable";
    access_log off;
}

location /uploads/ {
    alias /app/uploads/;
    expires 1d;
    add_header Cache-Control "public";
    access_log off;
}

# ── SocketIO (WebSocket + long-polling) ────────────────────
location /socket.io/ {
    proxy_pass http://myarea_app;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;
}

# ── Rate-limited endpoints ─────────────────────────────────
location /auth/login {
    limit_req zone=login burst=3 nodelay;
    proxy_pass http://myarea_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
}

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://myarea_app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
}

# ── Everything else → Flask ────────────────────────────────
location / {
    limit_req zone=game burst=30 nodelay;
    proxy_pass http://myarea_app;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_read_timeout 60;
    proxy_connect_timeout 10;
}
