#!/usr/bin/env bash
# Локальная сборка + деплой вручную. НЕ удаляет старые статьи.
set -euo pipefail
cd "$(dirname "$0")"

echo "🔨 Сборка..."
python3 build.py
python3 gen_sitemap.py

echo "📦 Коммит исходников..."
git add -A
git commit -m "Deploy $(date +%Y-%m-%d_%H%M)" || echo "(нечего коммитить)"
git push origin main

echo "✅ Готово. GitHub Actions опубликует output/ на Pages."
