#!/usr/bin/env bash
# Перегенерация статей новым (глубоким) промптом + критик
cd /Users/igor/project/fish-zone
unset PYTHONPATH
export PY=".venv/bin/python"

gen_and_critic() {
  local title="$1" cat="$2" tags="$3" slugfile="$4"
  rm -f "content/$slugfile.md"
  echo "════════ Генерация: $title ════════"
  $PY build.py --generate "$title" --category "$cat" --tags "$tags"
  # найти созданный файл
  local f=$(ls -t content/*.md | head -1)
  echo "  → $f ($(wc -c < "$f") байт)"
  bash run_critic.sh "$f" 2>&1 | tail -2
  echo ""
}

gen_and_critic "Как ловить судака на спиннинг: техника и снасти" "fish" "судак, ловля судака, спиннинг, джиг, хищник" "lovit-sudaka-spinning-tehnika-snasti"
gen_and_critic "Как ловить окуня на спиннинг: уловистые приёмы и приманки" "fish" "окунь, ловля окуня, спиннинг, микроджиг, хищник" "lovit-okunya-spinning-ulovistye-priyomy-primanki"
gen_and_critic "Джиг на спиннинге: техника ловли для начинающих" "technique" "джиг, техника ловли, спиннинг, джиг-головка, ступенька" "dzhig-spinninge-tehnika-lovli-nachinayuschih"
gen_and_critic "Как выбрать катушку для спиннинга: полный гид" "tackle" "катушка, выбор катушки, спиннинг, безынерционная" "vybrat-katushku-spinninga-polnyy-gid"

echo "════════ ИТОГ ════════"
for f in content/*.md; do echo "$(wc -c < "$f") байт  $f"; done
