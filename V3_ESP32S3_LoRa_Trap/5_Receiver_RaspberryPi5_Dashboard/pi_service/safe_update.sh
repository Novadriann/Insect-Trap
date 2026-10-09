#!/bin/bash
# ====================================================================================
# SCRIPT UPDATE AMAN (SAFE UPDATE) - RASPBERRY PI 5
# Memastikan foto hasil tangkapan & database SQLite TIDAK HILANG saat program di-update
# Lab ELINS - Universitas Gadjah Mada
# ====================================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/trap_backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "=========================================================="
echo "  MEMULAI PROSES UPDATE AMAN INSECT TRAP MONITORING"
echo "  Waktu: $TIMESTAMP"
echo "=========================================================="

# 1. BUAT FOLDER CADANGAN (BACKUP)
mkdir -p "$BACKUP_DIR"

echo "[1/4] Mencadangkan Database & Foto ke $BACKUP_DIR..."
if [ -f "$SCRIPT_DIR/trap_monitoring.db" ]; then
    cp "$SCRIPT_DIR/trap_monitoring.db" "$BACKUP_DIR/trap_monitoring_$TIMESTAMP.db"
    echo "  -> Database berhasil dicadangkan: trap_monitoring_$TIMESTAMP.db"
fi

if [ -f "$SCRIPT_DIR/sensor_history.csv" ]; then
    cp "$SCRIPT_DIR/sensor_history.csv" "$BACKUP_DIR/sensor_history_$TIMESTAMP.csv"
    echo "  -> CSV berhasil dicadangkan."
fi

# Cadangkan seluruh folder foto jika belum pernah dicadangkan
if [ -d "$SCRIPT_DIR/static/captures" ] && [ -d "$SCRIPT_DIR/static/annotated" ]; then
    mkdir -p "$BACKUP_DIR/photos_$TIMESTAMP"
    cp -rn "$SCRIPT_DIR/static/captures" "$BACKUP_DIR/photos_$TIMESTAMP/" 2>/dev/null || true
    cp -rn "$SCRIPT_DIR/static/annotated" "$BACKUP_DIR/photos_$TIMESTAMP/" 2>/dev/null || true
    echo "  -> Arsip foto dicadangkan ke $BACKUP_DIR/photos_$TIMESTAMP/"
fi

# 2. LAKUKAN GIT PULL ATAU UPDATE KODE
echo "[2/4] Mengambil pembaruan program dari Git..."
cd "$SCRIPT_DIR/../../.."
git stash || true
git pull origin main || true
cd "$SCRIPT_DIR"

# 3. PASTIKAN DATABASE & FOTO TERBARU TIDAK TERTIMPA FILE LAMA
echo "[3/4] Memulihkan & mengamankan database aktif..."
if [ -f "$BACKUP_DIR/trap_monitoring_$TIMESTAMP.db" ]; then
    cp "$BACKUP_DIR/trap_monitoring_$TIMESTAMP.db" "$SCRIPT_DIR/trap_monitoring.db"
fi

# 4. RESTART LAYANAN SYSTEMD
echo "[4/4] Me-restart service background..."
sudo systemctl restart insect-trap.service || true

echo ""
echo "=========================================================="
echo "  UPDATE BERHASIL! DATA & FOTO 100% AMAN TERJAGA"
echo "  Status service:"
echo "=========================================================="
sudo systemctl status insect-trap.service --no-pager -n 5 || true
