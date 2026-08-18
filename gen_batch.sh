#!/usr/bin/env bash
cd /Users/igor/project/fish-zone
unset PYTHONPATH
export PY=".venv/bin/python"

echo "════════ 1/3: Окунь ════════"
rm -f content/lovit-okunya-spinning-ulovistye-priyomy.md
$PY build.py --generate "Как ловить окуня на спиннинг: уловистые приёмы и приманки" --category fish --tags "окунь, ловля окуня, спиннинг, микроджиг, хищник"
bash run_critic.sh content/lovit-okunya-spinning-ulovistye-priyomy.md 2>&1 | tail -2

echo "════════ 2/3: Джиг ════════"
rm -f content/dzhig-tehnika-lovli-spinning.md
$PY build.py --generate "Джиг на спиннинге: техника ловли для начинающих" --category technique --tags "джиг, техника ловли, спиннинг, джиг-головка, ступенька"
bash run_critic.sh content/dzhig-tehnika-lovli-spinning.md 2>&1 | tail -2

echo "════════ 3/3: Катушка ════════"
rm -f content/kak-vybrat-katushku-spinning.md
$PY build.py --generate "Как выбрать катушку для спиннинга: полный гид" --category tackle --tags "катушка, выбор катушки, спиннинг, безынерционная"
bash run_critic.sh content/kak-vybrat-katushku-spinning.md 2>&1 | tail -2

echo "════════ ГОТОВО ════════"
ls -la content/*.md | awk '{print $NF, $5}'
