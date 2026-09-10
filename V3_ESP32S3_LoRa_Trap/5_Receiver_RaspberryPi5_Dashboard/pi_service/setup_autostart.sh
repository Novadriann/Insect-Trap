#!/bin/bash
# ====================================================================================
# SCRIPT SETUP AUTOSTART PEMANTAUAN HAMA DI RASPBERRY PI 5 (SYSTEMD SERVICE)
# Lab ELINS - Universitas Gadjah Mada
# ====================================================================================

echo "=== Memulai Konfigurasi Autostart Service Pemantauan Hama ==="

CURRENT_DIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/insect_trap.service"

echo "[1/4] Menginstall paket sistem pendukung..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv libgl1 libglib2.0-0

echo "[2/4] Menyiapkan Virtual Environment Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Membuat file konfigurasi systemd: $SERVICE_FILE"
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=Insect Trap Monitoring Service & Web Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 $CURRENT_DIR/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

echo "[4/4] Mengaktifkan dan menjalankan service..."
sudo systemctl daemon-reload
sudo systemctl enable insect_trap.service
sudo systemctl restart insect_trap.service

echo ""
echo "=== SELESAI! ==="
echo "Status Service saat ini:"
sudo systemctl status insect_trap.service --no-pager
echo ""
echo "Buka browser dan akses: http://$(hostname -I | awk '{print $1}'):5000"
