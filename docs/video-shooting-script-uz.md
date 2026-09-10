# Rejissyor Ssenariysi — 3:00

**Voice-to-Text OpenEMR** · rahbarga taqdimot
5 sahna · 2:45 nutq + 16 s harakat pauzalari ≈ **3:00**

> ### ⚠️ Kod ekranda ko'rsatilmaydi
> Butun texnik tushuntirish **diagrammalar orqali** beriladi. Video davomida
> hech qachon muharrir, terminal yoki fayl ochilmaydi — faqat ishlayotgan
> dastur va olti dona diagramma.

---

## Kerak bo'ladigan diagrammalar

Hammasi `docs/diagrams/` papkasida, mustaqil SVG fayl. Brauzerga sudrab
tashlab to'liq ekranda oching, yoki slaydga qo'ying.

| Fayl | Videoda | Nima ko'rsatadi |
|---|---|---|
| `1-arxitektura.svg` | `0:20` | Uch qism va ishonch chegarasi |
| `2-qatlamlar.svg` | `1:28`, `2:12` | Sakkiz qatlamli quvur |
| `3-gallyutsinatsiya.svg` | `1:44` | Tizim to'qilgan matnni qanday ushlaydi |
| `4-inkor-kodlash.svg` | `2:25` | Inkorni bilmaydigan tizim vs bizniki |
| `5-dori-tuzatish.svg` | *zaxira* | Savol-javob uchun |
| `6-holat.svg` | `2:41` | Nima ishlaydi, keyingi qadam nima |

**Maslahat:** oltala diagrammani **oldindan alohida tablarda** oching va
tartib bilan joylashtiring. Video davomida faqat `Cmd+1…6` bilan almashasiz —
fayl qidirib vaqt yo'qotmaysiz.

---

## Yozishdan oldin — 5 daqiqalik tayyorgarlik

**Terminal 1 — xizmat** *(kadr tashqarisida qoladi)*:
```bash
cd asr && uvicorn api:app --host 127.0.0.1 --port 8000
```

> ⚠️ Port 8000 sizda `Antimonopoliya` loyihasi tomonidan band bo'lishi mumkin.
> Avval uni to'xtating — kengaytma aynan 8000 ni kutadi.

**Terminal 2 — kengaytma** *(kadr tashqarisida qoladi)*:
```bash
npm run check && npm run build
```

**Ekranni tayyorlang:**

| ✓ | Nima |
|---|---|
| ☐ | Chrome → `chrome://extensions` → Developer Mode → `dist/extension` yuklangan |
| ☐ | **Tab 1:** OpenEMR encounter sahifasi |
| ☐ | **Tab 2–7:** oltala diagramma tartib bilan ochilgan |
| ☐ | Mikrofon ruxsati **oldindan** berilgan |
| ☐ | **Bitta sinov transkripsiyasi** qilingan — Whisper xotiraga yuklansin |
| ☐ | Panelda yashil nuqta va `Service ready` yozuvi bor |
| ☐ | Brauzer zoom **125%**, bildirishnomalar o'chirilgan |
| ☐ | **Muharrir va terminal yopilgan yoki boshqa ish stolida** |
| ☐ | Yozib olish: QuickTime yoki OBS, 1920×1080 |

**Muhim:** har sahnani alohida yozing. Sakkizta ekran almashuvi bor —
ularning har biri tabiiy kesish nuqtasi.

---

# SAHNA 1 · Muammo
### `0:00 → 0:20` · 46 so'z · **20 s**

> **EKRANDA**
> OpenEMR encounter sahifasi, bo'sh forma. `Reason for Visit` maydoni ko'rinsin.
> Panel yopiq yoki kadr tashqarisida.

> **HARAKAT**
> Harakat yo'q. Sichqoncha qimirlamasin — statik kadr.

**AYTASIZ:**

> "Shifokor ish vaqtining katta qismini bemor bilan emas — klaviatura bilan
> o'tkazadi.
>
> Biz OpenEMR'ga ovoz qatlamini qo'shdik: shifokor gapiradi, tizim yozadi.
>
> Bitta qat'iy shart bilan — bemor ma'lumoti bu kompyuterdan chiqmaydi.
> Hamma model lokal ishlaydi, hech qanday tashqi API yo'q."

---

# SAHNA 2 · Arxitektura
### `0:20 → 0:48` · 65 so'z · **28 s**

> **EKRANDA**
> **`1-arxitektura.svg`** — to'liq ekranda.

> **HARAKAT**
> Gapirayotganda sichqoncha bilan ketma-ket ko'rsating:
> **1)** chap quti · **2)** o'ng quti · **3)** pastki quti ·
> **4)** oxirida uzuq yashil chiziqni aylanib chiqing.

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

# SAHNA 3 · Jonli demo ⭐
### `0:48 → 1:28` · 57 so'z + ~16 s harakat · **40 s**

> **EKRANDA**
> OpenEMR encounter sahifasi. Panel o'ng pastda, yashil nuqta bilan.

Bu sahnada **kam gapiring** — harakat o'zi ko'rsatadi.

### `0:48` — Panelni tanishtiring *(4 s)*
> **HARAKAT:** sichqonchani panel status qatoriga olib boring.

> "Panel faqat to'ldiriladigan forma bor sahifada chiqadi — login ekranida
> umuman ko'rinmaydi."

### `0:52` — Yozib oling *(14 s)*
> **HARAKAT:** **Start mic** → aniq va sekin dikta qiling → **Stop**.

> *"Patient reports headache and mild fever for two days.
> She denies chest pain.
> On examination temperature 38 degrees, blood pressure 148 over 92, pulse 96.
> Impression is likely viral upper respiratory infection.
> Plan is acetaminophen 500 milligrams, continue lisinopril daily,
> follow up in one week."*

### `1:06` — Transkript keldi *(6 s)*
> **EKRANDA:** transkript + ostida **ASR ishonch chizig'i**.
> **HARAKAT:** ishonch chizig'ini sichqoncha bilan ko'rsating.

> "Transkript keldi. Ostida — modelning o'z ishonch darajasi."

### `1:12` — Tahlil *(4 s)*
> **HARAKAT:** **Analyze** bosing. Natija bir soniyadan kam vaqtda chiqadi.

### `1:16` — Eng muhim lahza *(8 s)*
> **EKRANDA:** maydonlar ro'yxati — har birida ✓, nom, **ishonch foizi**, qiymat.
> Tugmada: **Insert 10 fields**.
>
> **HARAKAT:** sichqonchani `diagnosis` qatoriga olib boring — u
> **belgilanmagan**, yonida `needs review`. Ikki soniya ushlab turing.

> "O'n bir maydon topildi. Lekin faqat o'ntasi belgilangan.
> Tashxis kodi belgilanmagan — chunki tizim o'zi unga ishonchi pastligini bildirdi."

### `1:24` — To'ldirish *(4 s)*
> **HARAKAT:** **Insert 10 fields** → tasdiqlash oynasi → **OK** →
> sahifani sekin pastga aylantiring (SOAP, keyin ko'rsatkichlar).

> "Bitta diktadan — butun forma. AI hech qachon kartaga o'zi yozmaydi:
> avval men ko'raman, keyin tasdiqlayman."

---

# SAHNA 4 · AI/ML qayerda ⭐⭐
### `1:28 → 2:41` · 170 so'z · **73 s**

Videoning eng muhim bo'limi. Rahbaringiz aynan shu javobni kutadi.
**Bu yerda kod ochilmaydi — faqat diagrammalar.**

### `1:28` — Umumiy ko'rinish *(16 s)*
> **EKRANDA** **`2-qatlamlar.svg`**
> **HARAKAT** Avval butun diagrammani, keyin pastdagi **legendani** ko'rsating:
> yashil = neyron model · kulrang = klassik algoritm · sariq = inson nazorati.

> "Sakkizta qatlam bor. Ikkitasi neyron tarmoq, qolgani klassik algoritm.
> Buni ochiq aytaman — regex bo'lgan narsani sun'iy intellekt deb atash halol emas.
>
> Birinchisi — **Whisper**, nutqni tanish modeli."

### `1:44` — Gallyutsinatsiya *(28 s)* — **eng kuchli lahza**
> **EKRANDA** **`3-gallyutsinatsiya.svg`**
> **HARAKAT** Yuqoridan pastga to'rt qatorni ko'rsating. Uchinchi qatorda
> **to'xtang**: avval yashil 80% chizig'ini, keyin qizil "TO'QILGAN" yorlig'ini
> ko'rsating. Oxirida pastdagi qizil izohni.

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
> **EKRANDA** **`2-qatlamlar.svg`** ga qayting.
> **HARAKAT** O'ngdagi beshta kulrang qutini yuqoridan pastga bir marta
> sichqoncha bilan supurib chiqing.

> "Qolgan beshta qatlam transkriptni klinik ma'lumotga aylantiradi: SOAP
> bo'limlari, dori nomlarini fonetik tuzatish, ko'rsatkichlarni tekshirish,
> inkor, ICD-10 kodlari va HIPAA identifikatorlari."

### `2:25` — Inkor → kodlash *(16 s)*
> **EKRANDA** **`4-inkor-kodlash.svg`**
> **HARAKAT** Yuqoridagi jumlani ko'rsating, keyin **chap ustunni** pastgacha
> (qizil natija), so'ng **o'ng ustunni** (yashil natija).

> "Eng muhim bog'lanish shu.
>
> 'Denies chest pain' ichida 'chest pain' so'zi bor. Buni tushunmaydigan tizim
> bemorga ko'krak og'rig'i kodini taklif qilardi — holbuki bemorda bu yo'q.
>
> Shuning uchun inkor tahlili kodlashdan **oldin** ishlaydi."

---

# SAHNA 5 · Holat va keyingi qadam
### `2:41 → 3:05` · 57 so'z · **24 s**

> **EKRANDA** **`6-holat.svg`**

> **HARAKAT**
> Yashil polosani ko'rsating → sariq qutiga o'ting →
> `"a seed of minifin"` yozuviga sichqonchani ushlab turing → o'ng qutiga.

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
| `0:00` | OpenEMR — bo'sh forma |
| `0:20` | `1-arxitektura.svg` |
| `0:48` | OpenEMR — panel + jonli demo |
| `1:28` | `2-qatlamlar.svg` |
| `1:44` | `3-gallyutsinatsiya.svg` |
| `2:12` | `2-qatlamlar.svg` *(qaytish)* |
| `2:25` | `4-inkor-kodlash.svg` |
| `2:41` | `6-holat.svg` |

Sakkizta almashuv — har biri kesish nuqtasi. Sahnalarni alohida yozib,
shu joylarda ulang.

---

## Savol-javob — rahbar chuqurroq so'rasa

Videodan keyin beriladigan savollarga tayyor javoblar. Kod **hali ham**
ochilmaydi — `5-dori-tuzatish.svg` diagrammasi shu uchun tayyorlangan.

**"Dori nomini qanday tuzatasiz?"**
→ `5-dori-tuzatish.svg` ni oching.
> "Uchta mustaqil o'lchov: harflar ketma-ketligi, talaffuz o'xshashligi va
> undoshlar skeleti. Ular birlashtiriladi. Lekin butunlay buzilgan nomni
> hech qanday o'lchov tiklay olmaydi — o'sha yerda model kerak."

**"Bu qanchalik ishonchli?"**
> "Qirq besh ta avtomatik test bor. Har biri ishlab chiqish davomida topilgan
> haqiqiy xatoni qoplaydi. Tahlil o'ttiz millisekundda tugaydi."

**"Bemor ma'lumoti xavfsizmi?"**
> "Audio ham, matn ham kompyuterdan chiqmaydi. Ustiga, tizim diktada aytilgan
> shaxsiy ma'lumotlarni — ism, tug'ilgan sana, telefon — alohida topib
> belgilaydi. HIPAA ro'yxati bo'yicha."

**"Xato qilsa nima bo'ladi?"**
> "Tizim hech qachon o'zi yozmaydi. Past ishonchli taklif o'zi yoqilmaydi —
> shifokor uni ongli ravishda belgilashi kerak. Demoda ko'rdingiz: o'n bir
> taklifdan biri belgilanmagan edi."

**"Qachon ishlatsak bo'ladi?"**
> "Hozir — prototip. Ishlab chiqarishga chiqarish uchun uchta narsa kerak:
> tibbiy ASR modeli, litsenziyalangan ICD-10 ma'lumotlar bazasi, va
> OpenEMR'ning o'z API'si orqali yozish."

---

## Chegaralarni to'g'ri ayting

So'rashsa yashirmang — muhandislik yetukligi bo'lib eshitiladi:

- **ICD-10 korpusi** — 91 ta koddan iborat namunaviy to'plam, litsenziyalangan
  CMS/CDC nashri emas
- **Dorilar ro'yxati** — 118 ta qo'lda tanlangan nom, to'liq RxNorm bazasi emas
- **Maydonlar** brauzer orqali to'ldiriladi, OpenEMR API'si orqali emas
- **Whisper** umumiy model — tibbiy terminlarda xato qiladi

---

## Agar vaqt yetmasa

Qisqartirish tartibi — **yuqoridan pastga**:

1. **Sahna 4, "Klinik qatlamlar"** (`2:12`) — 13 soniyani 6 ga: beshta qatlamni
   sanamasdan "beshta klinik qatlam" deb ayting.
2. **Sahna 2** — 28 soniyani 20 ga, uchta qismni tezroq sanang.
3. **Sahna 1** — "Hamma model lokal ishlaydi" jumlasini qisqartiring.

❌ **Demoni (Sahna 3) va gallyutsinatsiya qismini (`1:44`) hech qachon
qisqartirmang** — videoning ta'siri aynan shu ikkisida.

---

## Agar biror narsa ishlamasa

| Muammo | Nima qilasiz |
|---|---|
| Mikrofon ishlamadi | **Demo text** tugmasi — to'liq tahlil baribir ishlaydi |
| Xizmat o'chdi | Panelda "Service offline"; Demo text bilan davom eting |
| Transkript sekin | Whisper birinchi so'rovda yuklanadi — oldindan sinov qiling |
| Tahlil bo'sh qaytdi | Encounter sahifasida ekaningizni tekshiring |

**Nosozlikni videoda yashirmang.** Zaxira yo'lga o'tsangiz, ayting:
*"Xizmat o'chsa ham ish jarayoni uzilmaydi"* — bu kamchilik emas, dizayn.
