#!/usr/bin/env bash
cd /Users/igor/project/fish-zone
unset PYTHONPATH
export PY=".venv/bin/python"
rm -f content/vybrat-spinning-novichka-polnyy-gid-udilischu.md
echo "════════ Генерация: Спиннинг ════════"
$PY build.py --generate "Как выбрать спиннинг для новичка: полный гид по удилищу" --category tackle --tags "спиннинг, выбор спиннинга, новичок, удилище, тест, строй"
f=$(ls -t content/*.md | head -1)
echo "  → $f ($(wc -c < "$f") байт)"
echo "  директивы: $(grep -cE ':::' "$f")"
bash run_critic.sh "$f" 2>&1 | tail -2
echo "ИТОГ: $f"
