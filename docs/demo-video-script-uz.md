# 3 Daqiqalik Demo Video — Ssenariy

**Loyiha:** Voice-to-Text OpenEMR Integration
**Auditoriya:** rahbar (texnik emas, lekin arxitekturani tushunadi)
**Xronometraj:** 3:00 — beshta bo'lim

> Diagrammalar va "Ko'rsatish rejimi" bo'lgan versiya:
> https://claude.ai/code/artifact/5cbc3ae0-c2a6-4d63-a41a-a8ba1808b2d5
>
> Texnik chuqur tahlil (prezentatsiya oxiri uchun):
> [`ai-ml-architecture.md`](ai-ml-architecture.md)

---

## Yozishdan oldin

```bash
cd asr
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

```bash
npm run check && npm run build
```

Chrome → `chrome://extensions` → Developer Mode → **Load unpacked** → `dist/extension`

**Tekshiruv ro'yxati:**

- [ ] Mikrofon ruxsati **oldindan** berilgan
- [ ] **Bitta sinov transkripsiyasi** qilingan — Whisper birinchi so'rovda sekin yuklanadi
- [ ] Panel status qatorida "Service ready" yozuvi bor
- [ ] Brauzer zoom 110–125%, bildirishnomalar o'chirilgan
- [ ] `npm run check` yashil (45 test)

---

## 0:00 – 0:22 · Muammo va yechim  (~50 so'z)

**Ekranda:** OpenEMR encounter formasi.

> "Shifokor ish vaqtining katta qismini bemor bilan emas, klaviatura bilan o'tkazadi.
> Biz OpenEMR'ga ovozdan matnga o'tkazish qatlamini qo'shdik: shifokor gapiradi,
> tizim yozadi.
>
> Bitta shart bor — bemor ma'lumoti kompyuterdan chiqmasligi kerak. Shuning uchun
> barcha modellar lokal ishlaydi, hech qanday tashqi API yo'q."

---

## 0:22 – 0:50 · Arxitektura  (~63 so'z)

**Ekranda:** 1-diagramma (arxitektura).

> "Tizim uch qismdan iborat. Chapda — OpenEMR'ning o'z encounter formasi. O'ngda —
> Chrome kengaytmasi: sahifani skanerlab maydonlarni topadi va mikrofondan audio
> yozib oladi. Pastda — lokal FastAPI xizmati, sakkiz mingchi portda, ichida AI
> qatlamlari.
>
> Audio kengaytmadan xizmatga boradi, tahlil qaytadi, kengaytma esa formani
> to'ldiradi. Uzuq chiziqdan tashqariga hech narsa chiqmaydi."

---

## 0:50 – 1:32 · Jonli demo  (~68 so'z, harakat orasida)

**Ekranda:** encounter formasi + panel. Kam gapiring.

1. **Start mic** → dikta qiling:
   *"Patient reports headache and mild fever for two days. She denies chest pain.
   On examination temperature 38 degrees, blood pressure 148 over 92, pulse 96.
   Impression is likely viral upper respiratory infection.
   Plan is acetaminophen 500 milligrams, continue lisinopril daily, follow up in one week."*
2. **Stop** → transkript + **ASR ishonch chizig'i**
3. **Analyze** → bir soniyadan kam
4. **11 maydon topildi, 10 tasi belgilangan** — `diagnosis` belgilanmagan
5. **Insert 10 fields** → tasdiq → **OK**
6. SOAP + ko'rsatkichlar + dorilar — bitta diktadan

> "Bir marta gapiraman — va tizim butun encounter formasini to'ldiradi.
>
> Har bir maydon yonida ishonch foizi bor. E'tibor bering — o'n bir maydon topildi,
> lekin faqat o'ntasi belgilangan. Tashxis kodi belgilanmagan, chunki tizim o'zi
> unga ishonchi pastligini bildirdi.
>
> Bu asosiy tamoyil: past ishonchli taklif o'zi yoqilmaydi — shifokor uni ongli
> ravishda belgilashi kerak. AI hech qachon kartaga o'zi yozmaydi."

**Ko'rsating:** har qatorda `matched on name-attribute` — maydon OpenEMR'ning
haqiqiy `name` atributi bo'yicha topilgan, taxmin qilinmagan.

**Zaxira reja:** **Demo text** tugmasi — mikrofonsiz ham to'liq tahlil ishlaydi.

---

## 1:32 – 2:40 · AI/ML qatlamlari  (~150 so'z) ⭐

**Ekranda:** 2-diagramma (8 qatlam), keyin jadval.

> "Endi eng muhimi — AI qayerda. Sakkizta qatlam bor, ulardan ikkitasi neyron
> tarmoq, qolgani klassik algoritm. Buni ochiq aytaman, chunki regex bo'lgan
> narsani AI deb atash — halol emas.
>
> Birinchisi — **Whisper**, nutqni tanish modeli, kompyuterda ishlaydi.
>
> Ikkinchisi eng qiziq: **gallyutsinatsiyani aniqlash**. Whisper har segment uchun
> ichki statistika hisoblaydi, ko'pchilik uni tashlab yuboradi — biz o'qiymiz.
> Sukunat ustidan Whisper ba'zan matn to'qiydi. Haqiqiy sinovda
> *"thank you for watching, please subscribe"* chiqdi. Tizim buni ushladi.
>
> Keyingi qatlamlar transkriptni klinik ma'lumotga aylantiradi: SOAP bo'limlari,
> dori nomlarini fonetik tuzatish, ko'rsatkichlarni tekshirish, inkorni aniqlash,
> ICD-10 kodlarini taklif qilish, HIPAA identifikatorlarini topish.
>
> Eng muhim bog'lanish shu: agar shifokor 'ko'krak og'rig'i yo'q' desa, tizim
> buni tushunadi va o'sha kodni taklif qilmaydi."

### Ekranda ko'rsatiladigan kod

| Vaqt | Fayl | Nima |
|---|---|---|
| 1:50 | `asr/nlp/asr_quality.py` | Gallyutsinatsiya signallari |
| 2:05 | `asr/nlp/medical.py` | Soundex + tahrir masofasi |
| 2:18 | `asr/nlp/pipeline.py` | Inkor → kodlash bog'lanishi |
| 2:28 | `asr/nlp/coding.py` | Okapi BM25 |

### Sakkiz qatlam

| # | Qatlam | Texnika |
|---|---|---|
| 1 | Nutqni tanish | Whisper base — transformer *(neyron)* |
| 2 | ASR sifati | Dekoder statistikasi *(statistik)* |
| 3 | SOAP tuzilma | Ishora-ibora klassifikatori |
| 4 | Dori tuzatish | Soundex + tahrir masofasi |
| 5 | Inkor | NegEx (Chapman, 2001) |
| 6 | ICD-10 kodlash | Okapi BM25 |
| 7 | PHI aniqlash | Pattern + NER |
| 8 | Entity ajratish | spaCy NER / Llama 3.2 *(neyron, ixtiyoriy)* |

---

## 2:40 – 3:00 · Holat va keyingi qadam  (~48 so'z)

**Ekranda:** 3-diagramma.

> "Hozirgi holat: butun quvur ishlaydi — ovozdan formagacha, qirq besh ta test
> bilan qoplangan, tahlil o'ttiz millisekundda.
>
> Yagona ochiq nuqta: Whisper umumiy model bo'lgani uchun dori nomlarini buzadi.
> Sinovda *"acetaminophen"* *"a seed of minifin"* bo'lib chiqdi — buni hech qanday
> satr algoritmi tiklay olmaydi. Shuning uchun keyingi qadam — tibbiyotga
> moslashtirilgan model. Rahmat."

---

## Chegaralarni to'g'ri ayting

Bularni yashirmang — muhandislik yetukligi bo'lib eshitiladi:

- **ICD-10 korpusi 91 ta koddan iborat namunaviy to'plam**, litsenziyalangan
  CMS/CDC nashri emas.
- **Formulyar 118 ta qo'lda tanlangan dori**, RxNorm eksporti emas.
- **spaCy o'rnatilmagan bo'lsa** PHI ismlarni aniqlash zaifroq — xizmat buni
  `/capabilities` da ochiq bildiradi va panel "1 layer degraded" deb ko'rsatadi.
- **Maydonlar DOM orqali yoziladi**, OpenEMR API'si orqali emas.

---

## Yozib olish

- **Dastur:** QuickTime yoki OBS Studio, 1920×1080
- **Uslub:** har bo'limni alohida yozib, keyin birlashtiring
- **Tezlik:** o'zbek tilida ~140 so'z/daqiqa. Shoshilsangiz, 5-bo'limdan
  qisqartiring — demodan emas.
