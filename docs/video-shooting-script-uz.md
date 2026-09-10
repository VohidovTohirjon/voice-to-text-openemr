# Rejissyor Ssenariysi

**Voice-to-Text OpenEMR** · rahbarga taqdimot

Ikki versiya bir faylda:

| Versiya | Uzunlik | Qachon |
|---|---|---|
| **Asosiy** | `3:10` | Standart taqdimot |
| **Kengaytirilgan** | `5:47` | Rahbar texnik chuqurlik so'rasa |

> ### ⚠️ Kod ekranda ko'rsatilmaydi
> Butun texnik tushuntirish **diagrammalar orqali** beriladi. Video davomida
> muharrir, terminal yoki fayl ochilmaydi — faqat ishlayotgan OpenEMR va
> `docs/diagrams/` papkasidagi diagrammalar.

---

# 0. Oldindan tekshiruv — MAJBURIY

Yozib olishdan **oldin** bir marta to'liq o'tib chiqing. Panel OpenEMR ichida
iframe'da ishlaydi — buni oldindan ko'rmasangiz, yozuv paytida bilib qolasiz.

### 0.1 Uchta xizmat ko'tarilgan bo'lsin

```bash
# OpenEMR
open -a Docker
cd ~/openemr/docker/development-easy && docker compose up -d

# ASR/AI xizmati
cd ~/Documents/OpenEMR && ./run.sh
```

Tekshirish:

| Manzil | Kutilayotgan natija |
|---|---|
| `http://localhost:8300` | OpenEMR login sahifasi |
| `http://127.0.0.1:8000` | `{"service":"OpenEMR ASR...","status":"running"}` |

### 0.2 Kengaytma yuklangan bo'lsin

`chrome://extensions` da **OpenEMR Voice Capture 0.2.0** ko'rinib tursin,
tugmasi yoqilgan holatda.

### 0.3 Panel encounter formasida chiqishini tasdiqlang ⭐

1. `http://localhost:8300` → login (`admin`)
2. **Patient** → **Patients** → **Ivory Gomez**
3. **Encounters** → **New Encounter**
4. `Reason for Visit` maydonini toping — tepasida qizil
   **AI TRANSCRIPTION PLACEHOLDER** yozuvi turadi
5. **O'ng pastda qora panel chiqdimi?**

**Chiqsa** — tayyorsiz.

**Chiqmasa** — quyidagini tekshiring:

| Tekshiruv | Nima qilish |
|---|---|
| Manzil `https://` bilanmi? | `http://localhost:8300` ga o'ting — HTTPS'da ishlamaydi |
| Panel status qatorida nima yozilgan? | "Service offline" bo'lsa → `./run.sh status` |
| Konsolda xato bormi? | `Cmd+Option+J` → Console |

### 0.4 Whisper qizdirilgan bo'lsin

`./run.sh` buni avtomatik qiladi. Chiqishda shunday satr bo'lishi kerak:

```
Model xotirada (2.6 s): "Patient reports headache and mild fever for two days."
```

Bo'lmasa — demo paytida birinchi transkripsiya 30+ soniya kutadi.

### 0.5 Ekranni tozalang

| ✓ | Nima |
|---|---|
| ☐ | **Tab 1:** OpenEMR — **New Encounter formasi ochiq holatda** |
| ☐ | **Tab 2–7:** oltala diagramma tartib bilan |
| ☐ | Mikrofon ruxsati berilgan |
| ☐ | Muharrir va terminal yopilgan yoki boshqa ish stolida |
| ☐ | Bildirishnomalar o'chirilgan, brauzer zoom 125% |
| ☐ | Chrome'ning sariq "Developer mode" ogohlantirishi yopilgan |

> **Muhim:** login va bemor tanlash **yozuvdan oldin** bajariladi. Videoda
> ular ko'rinmaydi — video to'g'ridan-to'g'ri bo'sh encounter formasidan
> boshlanadi. Bu 25 soniya tejaydi va diqqatni chalg'itmaydi.

---

# ASOSIY VERSIYA — 3:10

2:54 nutq + 16 s harakat pauzalari = **3:10**.

## Kerak bo'ladigan diagrammalar

`docs/diagrams/` papkasida, mustaqil SVG. Brauzerga sudrab tashlang.

| Fayl | Videoda |
|---|---|
| `1-arxitektura.svg` | `0:20` |
| `2-qatlamlar.svg` | `1:28`, `2:12` |
| `3-gallyutsinatsiya.svg` | `1:44` |
| `4-inkor-kodlash.svg` | `2:25` |
| `6-holat.svg` | `2:41` |
| `5-dori-tuzatish.svg` | *zaxira — savol-javob uchun* |

---

## SAHNA 1 · Muammo
### `0:00 → 0:20` · 46 so'z

> **EKRANDA** OpenEMR — Ivory Gomez uchun bo'sh New Encounter formasi.
> `Reason for Visit` va qizil `AI TRANSCRIPTION PLACEHOLDER` ko'rinib tursin.
>
> **HARAKAT** Harakat yo'q. Statik kadr.

**AYTASIZ:**

> "Shifokor ish vaqtining katta qismini bemor bilan emas — klaviatura bilan
> o'tkazadi.
>
> Biz OpenEMR'ga ovoz qatlamini qo'shdik: shifokor gapiradi, tizim yozadi.
>
> Bitta qat'iy shart bilan — bemor ma'lumoti bu kompyuterdan chiqmaydi.
> Hamma model lokal ishlaydi, hech qanday tashqi API yo'q."

---

## SAHNA 2 · Arxitektura
### `0:20 → 0:48` · 65 so'z

> **EKRANDA** `1-arxitektura.svg`
>
> **HARAKAT** Ketma-ket ko'rsating: **1)** chap quti · **2)** o'ng quti ·
> **3)** pastki quti · **4)** uzuq yashil chiziqni aylanib chiqing.

**AYTASIZ:**

> "Tizim uch qismdan iborat.
>
> Chapda — OpenEMR'ning o'z encounter formasi.
>
> O'ngda — Chrome kengaytmasi: sahifadagi maydonlarni topadi va mikrofondan
> audio yozib oladi.
>
> Pastda — lokal xizmat, sakkiz mingchi portda. Ichida sakkizta tahlil qatlami.
>
> Audio kengaytmadan xizmatga boradi, tayyor tahlil qaytadi, kengaytma esa
> formani to'ldiradi.
>
> E'tibor bering — uzuq chiziqdan tashqariga hech narsa chiqmaydi."

---

## SAHNA 3 · Jonli demo ⭐
### `0:48 → 1:28` · 57 so'z + ~16 s harakat

> **EKRANDA** OpenEMR — New Encounter formasi, panel o'ng pastda.

### `0:48` — Panel *(4 s)*
> **HARAKAT** Sichqonchani panel status qatoriga olib boring
> (yashil nuqta + `Service ready`).

> "Panel faqat to'ldiriladigan forma bor sahifada chiqadi — login ekranida
> umuman ko'rinmaydi."

### `0:52` — Dikta *(14 s)*
> **HARAKAT** **Start mic** → aniq va sekin o'qing → **Stop**.

> *"Patient reports headache and mild fever for two days.
> She denies chest pain.
> On examination temperature 38 degrees, blood pressure 148 over 92, pulse 96.
> Impression is likely viral upper respiratory infection.
> Plan is acetaminophen 500 milligrams, continue lisinopril daily,
> follow up in one week."*

### `1:06` — Transkript *(6 s)*
> **EKRANDA** Transkript + **ASR ishonch chizig'i**
> **HARAKAT** Ishonch chizig'ini ko'rsating.

> "Transkript keldi. Ostida — modelning o'z ishonch darajasi."

### `1:12` — Tahlil *(4 s)*
> **HARAKAT** **Analyze** bosing.

### `1:16` — Eng muhim lahza *(8 s)*
> **EKRANDA** Maydonlar ro'yxati — ✓, nom, ishonch foizi, qiymat.
> **HARAKAT** `diagnosis` qatoriga sichqonchani olib boring — u
> **belgilanmagan**, yonida `needs review`. Ikki soniya ushlang.

> "Maydonlar topildi. Lekin hammasi belgilanmagan.
> Tashxis kodi belgilanmagan — chunki tizim o'zi unga ishonchi pastligini bildirdi."

### `1:24` — To'ldirish *(4 s)*
> **HARAKAT** **Insert** → tasdiqlash oynasi → **OK** →
> `Reason for Visit` maydoniga matn tushganini ko'rsating.

> "Bitta diktadan — forma to'ldi. AI hech qachon kartaga o'zi yozmaydi:
> avval men ko'raman, keyin tasdiqlayman."

---

## SAHNA 4 · AI/ML qayerda ⭐⭐
### `1:28 → 2:46` · 182 so'z · **78 s**

### `1:28` — Umumiy ko'rinish *(16 s)*
> **EKRANDA** `2-qatlamlar.svg`
> **HARAKAT** Butun diagramma, keyin pastdagi **legenda**:
> yashil = neyron model · kulrang = klassik algoritm · sariq = inson nazorati.

> "Sakkizta qatlam bor. Ikkitasi neyron tarmoq, qolgani klassik algoritm.
> Buni ochiq aytaman — regex bo'lgan narsani sun'iy intellekt deb atash halol emas.
>
> Birinchisi — **Whisper**, nutqni tanish modeli."

### `1:44` — Gallyutsinatsiya *(28 s)* — **eng kuchli lahza**
> **EKRANDA** `3-gallyutsinatsiya.svg`
> **HARAKAT** To'rt qatorni yuqoridan pastga. **Uchinchi qatorda to'xtang:**
> avval yashil 80% chizig'ini, keyin qizil "TO'QILGAN" yorlig'ini.
> Oxirida pastdagi qizil izohni.

> "Ikkinchisi eng qiziq. **Gallyutsinatsiyani aniqlash**.
>
> Whisper har bir segment uchun ichki statistika hisoblaydi. Ko'pchilik
> integratsiya uni tashlab yuboradi — biz o'qiymiz.
>
> Whisper sukunat ustidan ba'zan ravon matn to'qiydi. Bizning sinovimizda
> *'thank you for watching, please subscribe'* chiqdi — YouTube subtitrlaridan
> qolgan iz.
>
> Mana bu qatorga qarang: ishonch sakson foiz — yuqori. Lekin bu yerda umuman
> nutq yo'q edi.
>
> Shuning uchun biz uchta mustaqil signalni tekshiramiz. Tibbiy yozuvda
> to'qilgan gap yo'q gapdan xavfliroq — u fakt bo'lib o'qiladi."

### `2:12` — Klinik qatlamlar *(13 s)*
> **EKRANDA** `2-qatlamlar.svg` ga qayting.
> **HARAKAT** O'ngdagi beshta kulrang qutini bir marta supurib chiqing.

> "Qolgan beshta qatlam transkriptni klinik ma'lumotga aylantiradi: SOAP
> bo'limlari, dori nomlarini fonetik tuzatish, ko'rsatkichlarni tekshirish,
> inkor, ICD-10 kodlari va HIPAA identifikatorlari."

### `2:25` — Inkor → kodlash *(16 s)*
> **EKRANDA** `4-inkor-kodlash.svg`
> **HARAKAT** Yuqoridagi jumla → **chap ustun** pastgacha (qizil) →
> **o'ng ustun** (yashil).

> "Eng muhim bog'lanish shu.
>
> 'Denies chest pain' ichida 'chest pain' so'zi bor. Buni tushunmaydigan tizim
> bemorga ko'krak og'rig'i kodini taklif qilardi — holbuki bemorda bu yo'q.
>
> Shuning uchun inkor tahlili kodlashdan **oldin** ishlaydi."

---

## SAHNA 5 · Holat va keyingi qadam
### `2:46 → 3:10` · 57 so'z · **24 s**

> **EKRANDA** `6-holat.svg`
> **HARAKAT** Yashil polosa → sariq quti → `"a seed of minifin"` yozuvida
> ushlab turing → o'ng quti.

**AYTASIZ:**

> "Butun quvur ishlaydi — ovozdan formagacha. Qirq besh ta test, tahlil o'ttiz
> millisekundda.
>
> Yagona ochiq nuqta: Whisper umumiy model, dori nomlarini buzadi. Sinovda
> *'acetaminophen'* *'a seed of minifin'* bo'lib chiqdi.
>
> Buni satr algoritmi tiklay olmaydi — bu yerda model kerak. Keyingi qadam
> shu: tibbiyotga moslashtirilgan ASR modeli.
>
> Rahmat."

---

## Ekran almashuvlari — montaj uchun

| Vaqt | Nima ochiladi |
|---|---|
| `0:00` | OpenEMR — bo'sh New Encounter |
| `0:20` | `1-arxitektura.svg` |
| `0:48` | OpenEMR — jonli demo |
| `1:28` | `2-qatlamlar.svg` |
| `1:44` | `3-gallyutsinatsiya.svg` |
| `2:12` | `2-qatlamlar.svg` *(qaytish)* |
| `2:25` | `4-inkor-kodlash.svg` |
| `2:46` | `6-holat.svg` |

Sakkizta almashuv — har biri kesish nuqtasi.

---

# KENGAYTIRILGAN VERSIYA — 5:47

Asosiy versiyaning **ustiga** to'rtta qo'shimcha sahna qo'yiladi. Rahbar
"batafsilroq ko'rsating" desa yoki texnik auditoriya bo'lsa.

Joylashuvi: **Sahna 4 dan keyin, Sahna 5 dan oldin.**

---

## SAHNA 4A · Ko'rsatkichlar va fiziologik tekshiruv
### `+37 s` · 87 so'z

> **EKRANDA** OpenEMR — panel natijalari, ko'rsatkich qatorlari
> (`bp systolic 148`, `pulse 96`, `temperature 38.0`).

> "Diktadagi ko'rsatkichlar alohida ajratib olinadi va **birliklarga
> keltiriladi**. Masalan, 'temperature 38 degrees' desam — tizim buni Selsiy
> deb tushunadi. Agar '98.6' desam, Farengeyt deb tushunadi va o'giradi.
> Chunki 98 gradus Selsiy — tirik odamda bo'lmaydi.
>
> Bundan tashqari, har bir qiymat **fiziologik diapazonga** tekshiriladi.
> Agar transkripsiya buzilib, puls sakkiz yuz sakson bo'lib chiqsa, tizim buni
> qabul qilmaydi — 'bu transkripsiya xatosi' deb belgilaydi.
>
> Bu muhim, chunki raqamlar aynan nutqni tanishda buziladi. Va buzilgan raqam
> kartada haqiqat bo'lib qoladi."

---

## SAHNA 4B · Dori nomlarini tiklash
### `+43 s` · 99 so'z

> **EKRANDA** `5-dori-tuzatish.svg`
> **HARAKAT** Chap qutidan boshlang → uchta chiziqni ketma-ket →
> o'ng quti → pastdagi sariq izoh.

> "Whisper dori nomlarini doim buzadi. Bu uning aybi emas — u umumiy model,
> 'lisinopril' so'zini kamdan-kam eshitgan.
>
> Biz uchta mustaqil o'lchov bilan tiklaymiz.
>
> Birinchisi — **harflar ketma-ketligi**: qancha harf mos keladi.
>
> Ikkinchisi — **talaffuz**: ikki so'z quloqqa qanchalik bir xil eshitiladi.
> Bu muhim, chunki xatolar aynan tovushda bo'ladi.
>
> Uchinchisi — **undoshlar skeleti**: unlilarni tashlab, faqat undoshlarni
> solishtiramiz. Chunki nutqni tanishda birinchi bo'lib unlilar buziladi.
>
> Uchalasi birlashtiriladi. Lekin — mana bu qatorga qarang — butunlay buzilgan
> nomni hech qanday o'lchov tiklay olmaydi. O'sha yerda model kerak."

---

## SAHNA 4C · Maxfiylik va HIPAA
### `+41 s` · 95 so'z

> **EKRANDA** `1-arxitektura.svg` ga qayting, uzuq yashil chiziqni ko'rsating.

> "Maxfiylik haqida ikki narsa bor.
>
> Birinchisi — arxitektura. Audio ham, matn ham bu uzuq chiziqdan tashqariga
> chiqmaydi. Bulut yo'q, tashqi API yo'q. Ya'ni maxfiylik shartnoma hisobiga
> emas, tizimning tuzilishidan kelib chiqadi.
>
> Ikkinchisi — diktaning o'zi. Shifokor ovoz chiqarib o'ylayotganda kartaga
> tushmasligi kerak bo'lgan narsalarni aytadi: bemorning ismi, tug'ilgan sanasi,
> telefon raqami.
>
> Tizim ularni alohida topadi va belgilaydi — HIPAA ro'yxati bo'yicha. Hatto
> to'qson yoshdan katta yosh ham identifikator hisoblanadi, va u ham
> belgilanadi.
>
> Xohlasak, tizim matnning tozalangan nusxasini ham berishi mumkin."

---

## SAHNA 4D · Nega ishonsa bo'ladi
### `+36 s` · 83 so'z

> **EKRANDA** OpenEMR — panel, `needs review` yozuvi ko'rinadigan qator.

> "Oxirgi savol: bunday tizimga qanday ishonamiz?
>
> Uchta javob bor.
>
> Birinchisi — tizim **hech qachon o'zi yozmaydi**. Har bir maydon shifokor
> tasdig'idan o'tadi.
>
> Ikkinchisi — past ishonchli taklif **o'zi yoqilmaydi**. Uni belgilash uchun
> shifokor ongli harakat qilishi kerak. Ya'ni sukut saqlash 'ha' emas, 'yo'q'
> degani.
>
> Uchinchisi — qirq besh ta avtomatik test bor. Ularning har biri ishlab chiqish
> davomida topilgan **haqiqiy xatoni** qoplaydi. Xato topilganda test yoziladi,
> shunda u qaytib kelmaydi."

---

## Kengaytirilgan versiya — yakuniy xronometraj

| Sahna | Vaqt | Jami |
|---|---|---|
| 1 · Muammo | 20 s | `0:20` |
| 2 · Arxitektura | 28 s | `0:48` |
| 3 · Jonli demo | 40 s | `1:28` |
| 4 · AI/ML qatlamlari | 78 s | `2:46` |
| **4A · Ko'rsatkichlar** | **37 s** | `3:23` |
| **4B · Dori tiklash** | **43 s** | `4:06` |
| **4C · Maxfiylik** | **41 s** | `4:47` |
| **4D · Ishonch** | **36 s** | `5:23` |
| 5 · Holat va keyingi qadam | 24 s | `5:47` |

Vaqtlar o'lchangan: har sahnaning so'zlari sanalib, o'zbek tilida ~140 so'z/daqiqa
tezligiga bo'lingan. Taxmin emas.

---

# Savol-javob

Kod **hali ham** ochilmaydi.

**"Dori nomini qanday tuzatasiz?"** → `5-dori-tuzatish.svg`
> "Uchta mustaqil o'lchov: harflar ketma-ketligi, talaffuz va undoshlar
> skeleti. Birlashtiriladi. Butunlay buzilgan nomni esa hech biri tiklay
> olmaydi — o'sha yerda model kerak."

**"Bu qanchalik ishonchli?"**
> "Qirq besh ta avtomatik test. Har biri haqiqiy xatoni qoplaydi. Tahlil
> o'ttiz millisekundda tugaydi."

**"Bemor ma'lumoti xavfsizmi?"**
> "Audio ham, matn ham kompyuterdan chiqmaydi. Ustiga, tizim diktada aytilgan
> shaxsiy ma'lumotlarni topib belgilaydi — HIPAA ro'yxati bo'yicha."

**"Xato qilsa nima bo'ladi?"**
> "Tizim hech qachon o'zi yozmaydi. Past ishonchli taklif o'zi yoqilmaydi —
> shifokor uni ongli ravishda belgilashi kerak."

**"Boshqa tillar-chi?"**
> "Whisper ko'p tilli model — o'zbek tilini ham taniydi. Lekin klinik
> qatlamlar hozircha ingliz tili uchun sozlangan. Bu kengaytiriladigan ish."

**"Qachon ishlatsak bo'ladi?"**
> "Hozir — prototip. Ishlab chiqarishga uchta narsa kerak: tibbiy ASR modeli,
> litsenziyalangan ICD-10 bazasi, va OpenEMR'ning o'z interfeysi orqali yozish."

---

# Chegaralarni to'g'ri ayting

So'rashsa yashirmang — muhandislik yetukligi bo'lib eshitiladi:

- **ICD-10 korpusi** — 91 ta koddan iborat namunaviy to'plam, litsenziyalangan
  CMS/CDC nashri emas
- **Dorilar ro'yxati** — 118 ta qo'lda tanlangan nom, to'liq RxNorm bazasi emas
- **Maydonlar** brauzer orqali to'ldiriladi, OpenEMR API'si orqali emas
- **Whisper** umumiy model — tibbiy terminlarda xato qiladi
- **Klinik qatlamlar** ingliz tili uchun sozlangan

---

# Agar vaqt yetmasa

Qisqartirish tartibi — **yuqoridan pastga**:

1. **Sahna 4, "Klinik qatlamlar"** (`2:12`) — 13 soniyani 6 ga
2. **Sahna 2** — 28 soniyani 20 ga
3. **Sahna 1** — "Hamma model lokal ishlaydi" jumlasini qisqartiring

❌ **Demoni (Sahna 3) va gallyutsinatsiya qismini (`1:44`) hech qachon
qisqartirmang.**

---

# Agar biror narsa ishlamasa

| Muammo | Nima qilasiz |
|---|---|
| Panel chiqmadi | `http://` ekanini tekshiring (HTTPS'da ishlamaydi) |
| "Service offline" | `cd ~/Documents/OpenEMR && ./run.sh status` |
| Mikrofon ishlamadi | **Demo text** tugmasi — to'liq tahlil baribir ishlaydi |
| Transkript sekin | Whisper qizdirilmagan — `./run.sh` ni qayta ishlating |
| OpenEMR ochilmadi | Docker ishlayaptimi; konteyner `healthy` holatdami |
| Tahlil bo'sh qaytdi | Encounter formasida ekaningizni tekshiring |

**Nosozlikni videoda yashirmang.** Zaxira yo'lga o'tsangiz, ayting:
*"Xizmat o'chsa ham ish jarayoni uzilmaydi"* — bu kamchilik emas, dizayn.

---

# Yozib olish

- **Dastur:** QuickTime (File → New Screen Recording) yoki OBS Studio
- **Rezolyutsiya:** 1920×1080
- **Uslub:** har sahnani alohida yozing, montajda ulang
- **Tezlik:** o'zbek tilida ~140 so'z/daqiqa
