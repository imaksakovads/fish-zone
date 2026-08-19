# Супер-промт генерации изображений — Fish Zone (рабочая копия)

Каноническая версия: `Obsidian Vault/Спиннинг-блог/_Техническое/СУПЕР-ПРОМТ-изображений.md`

Структура промта (8 блоков):
1. Камера: `Professional editorial photograph shot on a full-frame DSLR (85mm f/1.8 lens), natural available light, shallow depth of field, RAW color grading.`
2. Сцена: место/время/погода/свет/фон
3. Субъект: точное описание (для рыбы — анатомия, см. ниже)
4. Действие
5. Композиция: `Wide 16:9 landscape composition, rule of thirds, balanced negative space for text overlay.`
6. Негатив: `NO text, NO watermark, NO logos, NO captions, NO extra limbs, NO deformed hands, NO duplicate objects, NO cartoonish style, NO oversaturation.`
7. Стиль: `Natural photorealistic, sharp focus, realistic colors, editorial fishing-magazine quality, no AI artifacts.`
8. Формат: `Wide 16:9 landscape.`

## Анатомия рыб (обязательно)
- ЩУКА: elongated body, flat duckbill snout, dorsal fin far back near tail, spotted olive back, light sides with dark spots
- СУДАК: long slender laterally-compressed body, pointed head, large mouth with sharp canine teeth, tall spiny dorsal fin in the MIDDLE (two dorsals), pale silver with faint dark vertical bands. NOT pike, NOT perch.
- ОКУНЬ: tall compressed body, two dorsal fins, dark vertical stripes, orange lower fins
- БЕРШ: like small zander, vertical bands, no canine teeth

## Снасти
- Спиннинг: graphite blank, reel seat, guide rings, cork/EVA handle
- Катушка: spinning reel with spool, bail arm, crank handle, mounted on rod
- Приманки: wobblers (minnow/crank), spinning/casting spoons, silicone vibrotail/twister on jig head

## Процесс
1. Собрать 8 блоков с анатомией
2. image_generate (FAL FLUX 2 Klein)
3. vision_analyze проверка (анатомия, артефакты)
4. Не та рыба → перегенерить с усиленной анатомией
5. Скачать → WebP 1344×768 q82 → static/images/
