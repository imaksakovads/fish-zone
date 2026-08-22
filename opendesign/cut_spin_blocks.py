#!/usr/bin/env python3
"""Удаляет чужой 'спиннинговый' блок (от 'Тест показывает' до '## FAQ') из статей."""
import re, os

content_dir = "/Users/igor/project/fish-zone/content"
targets = [
    "dzhig-spinninge-tehnika-lovli-nachinayuschih.md",
    "lovit-forel-spinning-snasti-primanki.md",
    "lovit-golavlya-spinning-taktika-primanki.md",
    "lovit-zhereha-spinning-polnoe-rukovodstvo.md",
    "otvodnoy-povodok-montazh-tehnika-lovli.md",
    "vyazat-rybolovnye-uzly-spinninga.md",
    "vybrat-blesnu-spinninga-kolebalki-vertushki.md",
    "vybrat-shnur-spinninga-pletyonka-vs-leska.md",
    "vybrat-vobler-spinninga-polnyy-gid.md",
]

markers = ["Тест показывает", "Тест удилища это диапазон"]
for f in targets:
    p = os.path.join(content_dir, f)
    txt = open(p, encoding="utf-8").read()
    
    # Найдём начало чужого блока
    start = None
    for mk in markers:
        idx = txt.find(mk)
        if idx != -1:
            start = idx
            break
    faq = txt.find("## FAQ")
    
    if start is not None and faq != -1 and start < faq:
        # Обрезаем от start до faq
        head = txt[:start].rstrip() + "\n\n## FAQ\n\n"
        open(p, "w", encoding="utf-8").write(head)
        print(f"{f}: удалён чужой блок ({len(txt)-len(head)} симв), теперь {len(head)}")
    else:
        print(f"{f}: не найдено (start={start}, faq={faq})")
