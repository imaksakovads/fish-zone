#!/usr/bin/env bash
# Полный пайплайн статьи Fish Zone.
#   ГЕНЕРАЦИЯ → КРИТИК → СБОРКА → ДЕПЛОЙ
# Использование:
#   bash pipeline.sh --generate "Заголовок" [--category tackle] [--tags "a, b"]
#   bash pipeline.sh                       # пересобрать + задеплоить всё
#   bash pipeline.sh --critic content/file.md
set -euo pipefail
cd "$(dirname "$0")"
unset PYTHONPATH

export PYTHON=".venv/bin/python"

echo "══════════════════════════════════════════"
echo " FISH ZONE — pipeline"
echo "══════════════════════════════════════════"

GENERATE=""
CATEGORY="tackle"
TAGS=""
PROMPT=""
CRITIC_FILE=""
for arg in "$@"; do
  case "$arg" in
    --generate) GENERATE="next" ;;
    --category=*) CATEGORY="${arg#*=}" ;;
    --tags=*) TAGS="${arg#*=}" ;;
    --prompt=*) PROMPT="${arg#*=}" ;;
    --critic=*) CRITIC_FILE="${arg#*=}" ;;
  esac
done

# Если --generate с заголовком
if [ "$GENERATE" = "next" ]; then
  TITLE=""
  for arg in "$@"; do
    if [ "$GENERATE" = "next" ] && [ "$arg" != "--generate" ]; then
      TITLE="$arg"; GENERATE="done"; break
    fi
  done
  [ -z "$TITLE" ] && { echo "Укажи заголовок после --generate"; exit 2; }
  echo "▶ Генерация: $TITLE"
  $PYTHON build.py --generate "$TITLE" --category "$CATEGORY" --tags "$TAGS" --prompt "$PROMPT"
  SLUG=$($PYTHON -c "import sys; sys.path.insert(0,'.'); import build; print(build.slugify('$TITLE'))")
  echo "▶ Критик: $SLUG"
  bash run_critic.sh "content/$SLUG.md" || echo "   (критик нашёл замечания — см. .critic/)"
fi

if [ -n "$CRITIC_FILE" ]; then
  echo "▶ Критик: $CRITIC_FILE"
  bash run_critic.sh "$CRITIC_FILE" || echo "   (есть замечания — см. .critic/)"
fi

echo "▶ Сборка"
$PYTHON build.py

echo "▶ Sitemap"
$PYTHON gen_sitemap.py

echo "▶ Git commit + push (Actions задеплоит)"
git add -A
git commit -m "Pipeline: $(date +%Y-%m-%d_%H%M)" >/dev/null 2>&1 || echo "   (нечего коммитить)"
git push origin main

echo "✅ Готово. Деплой через GitHub Actions."
