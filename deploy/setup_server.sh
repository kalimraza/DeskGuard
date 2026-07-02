#!/bin/bash
# DeskGuard Server Setup — Ubuntu 24.04
set -e

echo "[*] Installing dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx -qq

echo "[*] Setting up application..."
mkdir -p /opt/deskguard
cp -r ./server/* /opt/deskguard/
cd /opt/deskguard

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

mkdir -p /opt/deskguard/screenshots
mkdir -p /opt/deskguard/data
chmod 700 /opt/deskguard/screenshots

echo "[*] Creating systemd service..."
cat > /etc/systemd/system/deskguard.service << 'EOF'
[Unit]
Description=DeskGuard Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/deskguard
Environment="DATABASE_URL=sqlite:////opt/deskguard/data/monitor.db"
Environment="SCREENSHOT_STORAGE=disk"
Environment="SCREENSHOTS_DIR=/opt/deskguard/screenshots"
Environment="ADMIN_API_KEY=CHANGE_THIS_NOW"
ExecStart=/opt/deskguard/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chown -R www-data:www-data /opt/deskguard

systemctl daemon-reload
systemctl enable deskguard
systemctl start deskguard

echo "[*] Configuring nginx..."
cat > /etc/nginx/sites-available/deskguard << 'EOF'
server {
    listen 80;
    server_name monitor.yourdomain.com;
    client_max_body_size 100M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/deskguard /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo ""
echo "============================================"
echo " Server setup complete!"
echo "============================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Edit ADMIN_API_KEY in /etc/systemd/system/deskguard.service"
echo "   systemctl daemon-reload && systemctl restart deskguard"
echo ""
echo "2. Set your domain in /etc/nginx/sites-available/deskguard"
echo "   Then: certbot --nginx -d monitor.yourdomain.com"
echo ""
echo "3. Register first machine:"
echo "   cd /opt/deskguard"
echo "   source venv/bin/activate"
echo "   python cli.py addmachine --name DESKTOP-KALIM --notes 'Kalim machine'"
echo ""
echo "4. Paste the API key into agent/config.py on the Windows machine"
echo "   Also set SERVER_URL = 'https://monitor.yourdomain.com'"
echo "   And set MODE = 'hybrid'"
echo ""

# ── DigitalOcean firewall rules ───────────────────────────────────────────────
echo "[*] Configuring UFW firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh        # port 22
ufw allow http       # port 80  (nginx, redirects to HTTPS)
ufw allow https      # port 443 (nginx, actual traffic)
# Port 8000 (FastAPI) is NOT opened — only nginx can reach it
ufw --force enable
echo "Firewall configured. Only ports 22, 80, 443 are open."
