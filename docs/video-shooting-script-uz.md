# Rejissyor Ssenariysi — 3:00

**Voice-to-Text OpenEMR** · rahbarga taqdimot uchun
Jami xronometraj **~3:00** · 5 sahna · 395 so'z nutq

> Nutq o'lchandi: 2:45. Qolgani — Sahna 3 dagi bosish pauzalari.
> Shoshilmasangiz 3:05 chiqadi; aynan 3:00 kerak bo'lsa, Sahna 3 da
> lavhalar orasida ushlab turmang.

---

## Yozishdan oldin — 5 daqiqalik tayyorgarlik

**Terminal 1 — xizmat:**
```bash
cd asr && uvicorn api:app --host 127.0.0.1 --port 8000
```

> ⚠️ Port 8000 sizda `Antimonopoliya` loyihasi tomonidan band bo'lishi mumkin.
> Avval uni to'xtating — kengaytma aynan 8000 ni kutadi.

**Terminal 2 — kengaytma:**
```bash
npm run check && npm run build
```

**Ekranni tayyorlang:**

| ✓ | Nima |
|---|---|
| ☐ | Chrome → `chrome://extensions` → Developer Mode → `dist/extension` yuklangan |
| ☐ | Mikrofon ruxsati **oldindan** berilgan (video davomida dialog chiqmasin) |
| ☐ | **Bitta sinov transkripsiyasi** qilingan — Whisper xotiraga yuklansin |
| ☐ | Panelda yashil nuqta va `Service ready · Whisper base` yozuvi bor |
| ☐ | Brauzer zoom **125%**, bildirishnomalar o'chirilgan, ortiqcha tab yopilgan |
| ☐ | Diagramma sahifasi ikkinchi tabda ochiq, **Ko'rsatish rejimi yoqilgan** |
| ☐ | Yozib olish: QuickTime yoki OBS, 1920×1080 |

**Muhim:** har sahnani alohida yozing. 3 daqiqaga bir urinishda tushish qiyin,
montajda birlashtirish esa oson.

---

# SAHNA 1 · Muammo
### `0:00 → 0:20` · 46 so'z · **20 s**

> **EKRANDA**
> OpenEMR encounter sahifasi, bo'sh forma. `Reason for Visit` maydoni
> ko'rinib tursin. Panel hali yopiq (collapse) yoki kadr tashqarisida.

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
> Ikkinchi tabga o'ting → **1-diagramma** (arxitektura) to'liq ekranda.

> **HARAKAT**
> Gapirayotganda sichqoncha bilan qismlarni **ketma-ket ko'rsating**:
> 1. chap quti (OpenEMR sahifasi) → 2. o'ng quti (kengaytma) →
> 3. pastki quti (xizmat) → 4. oxirida uzuq chiziqni **aylanib chiqing**.

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
> OpenEMR encounter sahifasiga qayting. Panel o'ng pastda ochiq.
> Status qatorida yashil nuqta va `Service ready · Whisper base`.

Bu sahnada **kam gapiring** — harakat o'zi ko'rsatadi. Quyidagi tartibda:

### `0:48` — Panelni tanishtiring *(4 s)*
> **HARAKAT:** sichqonchani panel status qatoriga olib boring.

> "Panel faqat to'ldiriladigan forma bor sahifada chiqadi — login ekranida umuman ko'rinmaydi."

### `0:52` — Yozib oling *(14 s)*
> **HARAKAT:** **Start mic** bosing. Aniq va sekin dikta qiling:

> *"Patient reports headache and mild fever for two days.
> She denies chest pain.
> On examination temperature 38 degrees, blood pressure 148 over 92, pulse 96.
> Impression is likely viral upper respiratory infection.
> Plan is acetaminophen 500 milligrams, continue lisinopril daily,
> follow up in one week."*

> **HARAKAT:** **Stop** bosing.

### `1:06` — Transkript keldi *(6 s)*
> **EKRANDA:** transkript matni + ostida **ASR ishonch chizig'i** (foiz bilan).
> **HARAKAT:** ishonch chizig'ini sichqoncha bilan ko'rsating.

> "Transkript keldi. Ostida — modelning o'z ishonch darajasi."

### `1:12` — Tahlil *(4 s)*
> **HARAKAT:** **Analyze** bosing. Natija bir soniyadan kam vaqtda chiqadi.

### `1:16` — Eng muhim lahza *(8 s)*
> **EKRANDA:** maydonlar ro'yxati. Har birida ✓, nom, **ishonch foizi**, qiymat.
> Tugmada: **Insert 10 fields**.
>
> **HARAKAT:** sichqonchani `diagnosis` qatoriga olib boring —
> u **belgilanmagan** va yonida `needs review` yozuvi bor. Bir-ikki soniya ushlang.

> "O'n bir maydon topildi. Lekin faqat o'ntasi belgilangan.
> Tashxis kodi belgilanmagan — chunki tizim o'zi unga ishonchi pastligini bildirdi."

### `1:24` — To'ldirish *(4 s)*
> **HARAKAT:** **Insert 10 fields** → tasdiqlash oynasi chiqadi → ro'yxatni
> bir soniya ko'rsating → **OK**.
> **EKRANDA:** maydonlar ko'k ramka bilan yonib to'ladi.
> **HARAKAT:** sahifani sekin pastga aylantiring — SOAP, keyin ko'rsatkichlar.

> "Bitta diktadan — butun forma. AI hech qachon kartaga o'zi yozmaydi:
> avval men ko'raman, keyin tasdiqlayman."

---

# SAHNA 4 · AI/ML qayerda ⭐⭐
### `1:28 → 2:41` · 170 so'z · **73 s**

Videoning eng muhim bo'limi. Rahbaringiz aynan shu javobni kutadi.

### `1:28` — Umumiy ko'rinish *(16 s)*
> **EKRANDA** Ikkinchi tab → **2-diagramma** (8 qatlam).
> **HARAKAT** Avval butun diagrammani ko'rsating, keyin **legendani** —
> yashil = neyron model, kulrang = klassik algoritm, sariq = inson nazorati.

> "Sakkizta qatlam bor. Ikkitasi neyron tarmoq, qolgani klassik algoritm.
> Buni ochiq aytaman — regex bo'lgan narsani sun'iy intellekt deb atash halol emas.
>
> Birinchisi — **Whisper**, nutqni tanish modeli."

### `1:44` — Gallyutsinatsiya *(28 s)* — **eng kuchli lahza**
> **EKRANDA** `asr/nlp/asr_quality.py` faylini oching, boshidagi izohni ko'rsating.
> **HARAKAT** `no_speech_prob` qatorini belgilang.

> "Ikkinchisi eng qiziq. **Gallyutsinatsiyani aniqlash**.
>
> Whisper har bir segment uchun ichki statistika hisoblaydi. Ko'pchilik
> integratsiya uni tashlab yuboradi — biz o'qiymiz.
>
> Whisper sukunat ustidan ba'zan ravon matn to'qiydi. Bizning sinovimizda
> *'thank you for watching, please subscribe'* chiqdi — YouTube subtitrlaridan
> qolgan iz.
>
> Matn ishonchli ko'rinadi, lekin `no_speech_prob` nol nuqta sakson sakkiz.
> Tizim shundan ushlaydi.
>
> Tibbiy yozuvda to'qilgan gap yo'q gapdan xavfliroq — u fakt bo'lib o'qiladi."

### `2:12` — Klinik qatlamlar *(13 s)*
> **EKRANDA** Diagrammaga qayting, o'ngdagi beshta chipni ketma-ket ko'rsating.

> "Qolgan beshta qatlam transkriptni klinik ma'lumotga aylantiradi: SOAP
> bo'limlari, dori nomlarini fonetik tuzatish, ko'rsatkichlarni tekshirish,
> inkor, ICD-10 kodlari va HIPAA identifikatorlari."

### `2:25` — Inkor → kodlash *(16 s)*
> **EKRANDA** `asr/nlp/pipeline.py`, `excluded_negated_findings` qatori.

> "Eng muhim bog'lanish shu.
>
> 'Denies chest pain' ichida 'chest pain' so'zi bor. Buni tushunmaydigan tizim
> bemorga ko'krak og'rig'i kodini taklif qilardi — holbuki bemorda bu yo'q.
>
> Shuning uchun inkor tahlili kodlashdan **oldin** ishlaydi."

---

# SAHNA 5 · Holat va keyingi qadam
### `2:41 → 3:05` · 57 so'z · **24 s**

> **EKRANDA**
> **3-diagramma** — yuqorida yashil "to'liq ishlaydi" polosasi,
> pastda sariq "yagona ochiq nuqta" qutisi.

> **HARAKAT**
> Yashil polosani ko'rsating → keyin sariq qutiga o'ting va
> `"a seed of minifin"` yozuviga sichqonchani ushlab turing.

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

## Ekran almashuvlari — qisqa jadval

| Vaqt | Tab | Nima ko'rinadi |
|---|---|---|
| `0:00` | OpenEMR | Bo'sh encounter formasi |
| `0:20` | Diagramma | 1 — arxitektura |
| `0:48` | OpenEMR | Panel + jonli demo |
| `1:28` | Diagramma | 2 — 8 qatlam |
| `1:44` | Kod | `asr/nlp/asr_quality.py` |
| `2:12` | Diagramma | 2 — o'ng chiplar |
| `2:25` | Kod | `asr/nlp/pipeline.py` |
| `2:41` | Diagramma | 3 — holat va keyingi qadam |

Sakkizta almashuv. Har birini montajda kesish nuqtasi deb hisoblang —
sahnalarni alohida yozib, shu joylarda ulang.

---

## Agar vaqt yetmasa

Qisqartirish tartibi — **yuqoridan pastga**:

1. **Sahna 4, "Klinik qatlamlar"** (`2:12`) — 13 soniyani 6 ga tushiring:
   beshta qatlamni sanamasdan "beshta klinik qatlam" deb ayting.
2. **Sahna 2** — 28 soniyani 20 ga, uchta qismni tezroq sanang.
3. **Sahna 1** — "Tibbiy tizimda bu asosiy talab" jumlasi allaqachon olib
   tashlangan; keyingi navbatda "Hamma model lokal ishlaydi" ni qisqartiring.

❌ **Demoni (Sahna 3) va gallyutsinatsiya qismini (`1:44`) hech qachon
qisqartirmang** — videoning ta'siri aynan shu ikkisida.

---

## Agar biror narsa ishlamasa

| Muammo | Nima qilasiz |
|---|---|
| Mikrofon ishlamadi | **Demo text** tugmasi — to'liq tahlil baribir ishlaydi |
| Xizmat o'chdi | Panelda "Service offline" chiqadi; Demo text bilan davom eting |
| Transkript sekin | Whisper birinchi so'rovda yuklanadi — oldindan sinov qiling |
| Tahlil bo'sh qaytdi | Sahifada to'ldiriladigan maydon yo'q; encounter sahifasiga o'ting |

**Bu nosozliklarni videoda yashirmang.** Agar zaxira yo'lga o'tsangiz, ayting:
*"Xizmat o'chsa ham ish jarayoni uzilmaydi"* — bu kamchilik emas, dizayn.

---

## Prezentatsiya oxiri uchun — texnik ilova

Rahbaringiz batafsil so'rasa:

- **`docs/ai-ml-architecture.md`** — har bir qatlamning texnikasi, nega aynan shu
  usul tanlangani (masalan, nega BM25 embedding'dan yaxshiroq), va chegaralar.
- **`python3 asr/tests/run_tests.py -v`** — 45 ta test, Whisper va internetsiz ishlaydi.
- **`curl http://127.0.0.1:8000/capabilities`** — qaysi qatlam ishlayotgani.

**Chegaralarni ochiq ayting** — bu muhandislik yetukligi bo'lib eshitiladi:

- ICD-10 korpusi — 91 ta koddan iborat namunaviy to'plam, litsenziyalangan nashr emas
- Formulyar — 118 ta qo'lda tanlangan dori, RxNorm eksporti emas
- Maydonlar DOM orqali yoziladi, OpenEMR API'si orqali emas
