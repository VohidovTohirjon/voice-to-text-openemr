# Diagrammalar

Taqdimotga qo'yish uchun mustaqil SVG fayllar. Ranglari qat'iy belgilangan
(CSS o'zgaruvchilari yo'q), shuning uchun PowerPoint, Keynote, Google Slides,
Canva va brauzerda bir xil ko'rinadi.

| Fayl | Nima ko'rsatadi | Videoda |
|---|---|---|
| `1-arxitektura.svg` | Uch qism va ishonch chegarasi | `0:20` |
| `2-qatlamlar.svg` | Sakkiz qatlamli quvur | `1:28` |
| `3-gallyutsinatsiya.svg` | Whisper qanday matn to'qiydi va biz uni qanday ushlaymiz | `1:44` |
| `4-inkor-kodlash.svg` | Inkorni bilmaydigan tizim vs bizniki | `2:25` |
| `5-dori-tuzatish.svg` | Mis-heard dori nomi qanday tiklanadi | zaxira |
| `6-holat.svg` | Nima ishlaydi, keyingi qadam nima | `2:41` |

## Ishlatish

**Brauzerda ko'rish:** faylni Chrome'ga sudrab tashlang.

**PNG ga o'girish** (agar slayd dasturi SVG ni qabul qilmasa):

```bash
# macOS, qo'shimcha dastursiz
qlmanage -t -s 2400 -o docs/diagrams docs/diagrams/1-arxitektura.svg
```

yoki brauzerda ochib, to'liq ekranda skrinshot oling (Cmd+Shift+4).

**O'lchamlar:** hammasi 900 px kenglikda chizilgan, cheksiz kattalashadi.
Slaydda 16:9 kadrga to'liq sig'adi.

## Tahrirlash

Oddiy matn fayllari — istalgan muharrirda ochib matnni o'zgartirsangiz bo'ladi.
Ranglar har faylning boshida izohda sanab o'tilgan.

## Tayyor eksportlar

SVG'lar yonida tayyor fayllar ham turadi — hech narsa o'girish shart emas:

| Fayl | Nima uchun |
|---|---|
| `arxitektura-diagrammalar.pdf` | **Oltala diagramma, 6 sahifa.** Chrome'da ochiladi, rahbarga yuborsa ham bo'ladi |
| `*.png` | Har biri alohida, 1800 px kenglikda — slaydga qo'yish uchun |

**Chrome'da ochish:** faylni Chrome oynasiga sudrab tashlang, yoki ustiga o'ng
tugma → *Open With* → *Google Chrome*.

## Qayta yaratish

SVG'ni tahrirlaganingizdan keyin:

```bash
cd docs/diagrams
rsvg-convert -f pdf -o arxitektura-diagrammalar.pdf \
  1-arxitektura.svg 2-qatlamlar.svg 3-gallyutsinatsiya.svg \
  4-inkor-kodlash.svg 5-dori-tuzatish.svg 6-holat.svg
for f in *.svg; do rsvg-convert -f png -z 2 -o "${f%.svg}.png" "$f"; done
```

`rsvg-convert` yo'q bo'lsa: `brew install librsvg`

Shriftlar tizimnikiga tushadi (Helvetica / Menlo) — ataylab shunday, hech qanday
shrift o'rnatish talab qilinmaydi.
