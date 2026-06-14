#!/bin/bash
# ============================================================
# install.sh — Daily Briefing App
# ============================================================
set -e

APP_DIR="$HOME/.daily-briefing"
APP_FILE="daily_briefing_app.py"
DEST="$APP_DIR/$APP_FILE"

echo ""
echo "☀️  Installation de Daily Briefing..."
echo ""

# 1. Trouver un Python 3.10+ (rumps ne supporte pas Python 3.9)
echo "→ Recherche d'un Python compatible (3.10+)..."

PYTHON=""
for candidate in \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /usr/local/bin/python3.13 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "❌  Aucun Python 3.10+ trouvé."
    echo ""
    echo "Installe Python via Homebrew puis relance :"
    echo "  brew install python@3.12"
    echo "  ./install.sh"
    exit 1
fi

echo "  ✓ Python trouvé : $PYTHON ($($PYTHON --version))"

# 2. Créer le dossier et le venv
echo "→ Création de l'environnement virtuel dans ~/.daily-briefing/venv..."
mkdir -p "$APP_DIR"
"$PYTHON" -m venv "$APP_DIR/venv"
VENV_PYTHON="$APP_DIR/venv/bin/python3"
echo "  ✓ venv créé"

# 3. Installer rumps dans le venv (pyobjc inclus — sert aussi pour la fenêtre settings)
echo "→ Installation de rumps dans le venv..."
"$VENV_PYTHON" -m pip install rumps --quiet
echo "  ✓ rumps installé"

# 4. Copier l'app
echo "→ Copie de l'app vers ~/.daily-briefing/..."
cp "$APP_FILE" "$DEST"
chmod +x "$DEST"
echo "  ✓ App copiée dans $APP_DIR"

# 4b. Créer la config par défaut si elle n'existe pas encore
CONFIG_FILE="$APP_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<'EOFCFG'
{
  "days": [0, 1, 2, 3, 4],
  "hour": 9,
  "minute": 0,
  "spotify_uri": "spotify:playlist:37i9dQZF1DX4sWSpwq3LiO",
  "music_delay": 10,
  "alarm_volume": 80,
  "voice": "Thomas"
}
EOFCFG
    echo "  ✓ Config par défaut créée dans $CONFIG_FILE"
else
    echo "  ✓ Config existante conservée"
fi

# Remplacer $PYTHON par le python du venv pour la suite
PYTHON="$VENV_PYTHON"

# 5. Installer le LaunchAgent menubar (démarrage automatique au login)
MENUBAR_PLIST="$HOME/Library/LaunchAgents/com.fairforge.daily-briefing-menubar.plist"
echo "→ Configuration du démarrage automatique..."

cat > "$MENUBAR_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fairforge.daily-briefing-menubar</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$DEST</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/daily-briefing-menubar.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily-briefing-menubar-error.log</string>
</dict>
</plist>
EOF

launchctl unload "$MENUBAR_PLIST" 2>/dev/null || true
launchctl load "$MENUBAR_PLIST"
echo "  ✓ App configurée pour démarrer automatiquement au login"

# 6. Lancer l'app tout de suite dans la menubar
echo "→ Lancement de l'app..."
"$PYTHON" "$DEST" &
sleep 2

echo ""
echo "✅ Installation terminée !"
echo ""
echo "☀️  L'icône Daily Briefing est maintenant dans ta menubar."
echo "Elle démarrera automatiquement à chaque ouverture de session."
echo ""
echo "N'oublie pas de mettre à jour ta tâche Cowork 'daily-breifing'"
echo "avec le contenu du fichier SKILL-daily-briefing-updated.md"
