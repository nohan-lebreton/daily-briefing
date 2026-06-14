# ☀️ Daily Briefing

App menubar macOS — réveil intelligent avec Spotify + résumé de l'agenda parlé à voix haute.

## Ce que ça fait

1. À l'heure configurée, ouvre Spotify sur la playlist choisie au volume désiré
2. Après quelques secondes, baisse la musique et lit ton agenda du jour à voix haute (via la voix Thomas)
3. Reprend la musique à plein volume une fois le brief terminé
4. Une icône dans la menubar donne accès aux paramètres

## Prérequis

- macOS 12+
- [Homebrew](https://brew.sh)
- Python 3.10+ via Homebrew : `brew install python@3.12`
- Spotify installé
- La tâche Cowork `daily-breifing` configurée (écrit le résumé dans `~/daily-briefing-summary.txt`)

## Installation

```bash
git clone https://github.com/nohan-lebreton/daily-briefing.git
cd daily-briefing
chmod +x install.sh
./install.sh
```

L'app démarre automatiquement et se relance à chaque ouverture de session.

## Paramètres

Clic sur l'icône ☀️ dans la menubar → **Paramètres…**

| Réglage | Description |
|---|---|
| Jours actifs | Jours de la semaine où l'alarme se déclenche |
| Heure | Heure de déclenchement |
| URI Spotify | Playlist ou titre (clic droit → Partager → Copier l'URI) |
| Durée avant le brief | Secondes de musique avant la lecture du résumé |
| Volume réveil | Volume Spotify pendant le réveil |
| Voix | Voix macOS pour la lecture (Thomas, Amélie, Nathalie) |
| Volume de la voix | Volume du TTS |
| URL GitHub | URL raw du fichier pour les mises à jour automatiques |

## Mise à jour

Ouvrir les Paramètres → cliquer **Mettre à jour** — l'app télécharge automatiquement la dernière version depuis ce repo et redémarre.

## Fichiers

```
~/.daily-briefing/
├── daily_briefing_app.py   # App principale
├── config.json             # Paramètres (éditable manuellement)
├── venv/                   # Environnement Python isolé
└── icon.png                # Icône menubar

~/Library/LaunchAgents/
├── com.fairforge.daily-briefing-menubar.plist   # Démarrage auto
└── com.fairforge.daily-briefing.plist           # Alarme planifiée
```

## Désinstallation

```bash
launchctl unload ~/Library/LaunchAgents/com.fairforge.daily-briefing-menubar.plist
launchctl unload ~/Library/LaunchAgents/com.fairforge.daily-briefing.plist
rm -rf ~/.daily-briefing
rm ~/Library/LaunchAgents/com.fairforge.daily-briefing*.plist
```
