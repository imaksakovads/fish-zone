#!/usr/bin/env bash
# Волна 1: 6 статей (жерех, берш, сом, шнур, узлы, поводок)
cd /Users/igor/project/fish-zone
unset PYTHONPATH
export PY=".venv/bin/python"

gen() {
  local title="$1" cat="$2" tags="$3" slug="$4"
  rm -f "content/$slug.md"
  echo "═══ Генерация: $title ═══"
  $PY build.py --generate "$title" --category "$cat" --tags "$tags" 2>&1 | grep -E "Гуманизатор ответил|байт|Создана"
  local f="content/$slug.md"
  echo "  → $(wc -c < "$f") байт, директивы: $(grep -cE ':::' "$f")"
  bash run_critic.sh "$f" 2>&1 | grep -E "Verdict|FAIL|PASS" | head -1
  echo ""
}

# Рыбы
gen "Как ловить жереха на спиннинг: полное руководство" "fish" "жерех, ловля жереха, спиннинг, приманки, хищник" "lovit-zhereha-spinning-polnoe-rukovodstvo"
gen "Как ловить берша на спиннинг: техника и снасти" "fish" "берш, ловля берша, спиннинг, джиг, судак" "lovit-bersha-spinning-tehnika-snasti"
gen "Как ловить сома на спиннинг: снасти и тактика" "fish" "сом, ловля сома, спиннинг, квок, хищник" "lovit-soma-spinning-snasti-taktika"

# Снасти
gen "Как выбрать шнур для спиннинга: плетёнка vs леска" "tackle" "шнур, плетенка, выбор шнура, леска, спиннинг" "vybrat-shnur-spinninga-pletenka-leska"
gen "Как вязать рыболовные узлы для спиннинга" "rig" "узлы, как вязать, плетенка, крючок, вертлюжок" "vyazat-rybolovnye-uzly-spinning"
gen "Как выбрать и привязать поводок для спиннинга" "rig" "поводок, как привязать, флюорокарбон, спиннинг" "vybrat-priyazat-povodok-spinning"

echo "═══ ВОЛНА 1 ГОТОВА ═══"
