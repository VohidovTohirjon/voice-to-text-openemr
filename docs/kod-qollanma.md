# Kodni o'rganish qo'llanmasi

Rahbarga tushuntirishdan oldin o'zingiz bilib olishingiz uchun. Har bo'limda
**o'zingiz ishga tushirib ko'radigan buyruq** bor. O'qigandan ko'ra ishlatib
ko'rish tezroq tushuntiradi.

Boshlashdan oldin:

```bash
cd ~/Documents/OpenEMR/asr
```

Quyidagi barcha Python buyruqlari shu papkadan ishlatiladi.

---

## 0. Katta rasm

Uch qism bor:

| Qism | Qayerda | Vazifasi |
|---|---|---|
| Chrome kengaytmasi | `extension/` | Ovoz yozadi, formadagi maydonlarni topadi, to'ldiradi |
| Tahlil xizmati | `asr/` | Ovozni matnga, matnni klinik ma'lumotga aylantiradi |
| OpenEMR o'zgarishlari | `openemr/modified_files/` | Encounter formasiga joy ochib beruvchi ikki fayl |

Kengaytma xizmatga HTTP orqali murojaat qiladi. Boshqa aloqa yo'q.

---

## 1. Modellar: qaysi biri, qayerda, nima uchun

Loyihada **uchta** model bor. Ikkitasi doim ishlaydi, biri ixtiyoriy.

| Model | Fayl | Qator | Nima qiladi | Majburiymi |
|---|---|---|---|---|
| **Whisper base** | `api.py` | 62 | Ovozni matnga aylantiradi | Ha |
| **spaCy `en_core_web_sm`** | `phi.py` | 109 | Matndan ism va joy nomlarini topadi | Yo'q |
| **Llama 3.2 3B** | `soap.py` | 331 | SOAP bo'limlarga ajratishning muqobil yo'li | Yo'q |

Qolgan **beshta qatlam model emas**, oddiy algoritm. Buni bilib turish muhim,
chunki rahbar "bu yerda qanaqa AI bor" deb so'rasa, aniq javob berasiz.

**Tekshirib ko'ring:**

```bash
curl -s http://127.0.0.1:8000/capabilities | python3 -m json.tool
```

Xizmat o'zi qaysi qatlam tirikligini aytadi. `entity_extraction` da
`"available": false` chiqadi, chunki spaCy o'rnatilmagan. Tizim buni yashirmaydi.

---

## 2. O'qish tartibi

Fayllarni shu tartibda o'qing. Har biri oldingisiga tayanadi.

1. `asr/nlp/prompting.py` (138 qator) — eng qisqa va eng muhim g'oya
2. `asr/nlp/asr_quality.py` (240) — modelning o'ziga ishonchni o'lchash
3. `asr/nlp/medical.py` (680) — eng katta, lekin to'rt mustaqil bo'lakdan iborat
4. `asr/nlp/soap.py` (414) — matnni bo'limlarga ajratish
5. `asr/nlp/coding.py` (242) — tashxis kodlarini topish
6. `asr/nlp/phi.py` (279) — shaxsiy ma'lumotlarni aniqlash
7. `asr/nlp/pipeline.py` (379) — hammasini birlashtiradi
8. `api.py` (334) — tashqi interfeys

Kengaytmani keyinroq qoldiring, u mustaqil.

---

## 3. Qatlamlar

### 3.1 Whisper va uni yo'naltirish

**Fayl:** `asr/nlp/prompting.py`, ishlatilishi `asr/api.py:66`

Whisper umumiy model. Uni qayta o'qitmasdan, har bir so'rovda oldiga klinik
lug'at qo'yamiz. Model o'zi o'zgarmaydi, faqat shu so'rov uchun "keyingi so'z
nima bo'lishi mumkin" degan ehtimol siljiydi.

Uch sozlama:

| Sozlama | Nima uchun |
|---|---|
| `initial_prompt` | Klinik lug'at, formulyardan yasaladi |
| `language="en"` | Til aniqlash erkin qolsa, boshqa alifboda yozib yuborardi |
| `temperature=0` | Bir xil audio har doim bir xil natija bersin |

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.prompting import clinical_prompt, decode_options
print(clinical_prompt()[:240])
print()
print({k: v for k, v in decode_options().items() if k != 'initial_prompt'})
"
```

Ko'rasiz: prompt oddiy matn, formulyardagi dori nomlari ro'yxati.

### 3.2 Modelning o'ziga ishonchi

**Fayl:** `asr/nlp/asr_quality.py:105`

Whisper har bir segment uchun uchta ichki raqam chiqaradi va ko'pchilik
integratsiya ularni tashlab yuboradi. Biz o'qiymiz.

| Raqam | Ma'nosi | Chegara (`asr/nlp/asr_quality.py:41`) |
|---|---|---|
| `avg_logprob` | So'zlarni qanchalik ishonch bilan tanlagani | −1.0 dan past |
| `compression_ratio` | Matn qanchalik takrorlanuvchan | 2.4 dan yuqori |
| `no_speech_prob` | Bu yerda umuman nutq bo'lganmi | 0.6 dan yuqori |

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.asr_quality import analyze_segments
r = analyze_segments([{
 'start':0,'end':6,'text':'follow up follow up follow up follow up follow up',
 'avg_logprob':-0.62,'compression_ratio':1.9,'no_speech_prob':0.08}])
s = r['segments'][0]
print('gallyutsinatsiya:', s['hallucination_suspected'])
print('sabab:', s['reasons'])
"
```

### 3.3 Klinik lug'at

**Fayl:** `asr/nlp/medical.py` — to'rt mustaqil bo'lak

| Bo'lak | Qator | Nima qiladi |
|---|---|---|
| Qisqartmalar | 97 | `HTN` → hypertension, xavfli qisqartmalarni ogohlantiradi |
| Dori nomlari | 260 | Noto'g'ri eshitilgan nomni formulyardan topadi |
| Ko'rsatkichlar | 425 | Birlikka keltiradi va fiziologik chegarani tekshiradi |
| Inkor | 601 | "yo'q" degan so'zni tushunadi |

Dori nomi uchta o'lchov bilan solishtiriladi (`asr/nlp/medical.py:192`):
yozilish o'xshashligi 55%, talaffuz 20%, undoshlar skeleti 25%.

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.medical import correct_medications, extract_vitals, detect_negation
for t in ['Continue metform in 1000 mg daily.', 'Continue lysinopril 10mg daily.']:
    m = correct_medications(t)[0]
    print(repr(m['heard']), '->', m['suggestions'][0]['name'], m['source'])
print()
for v in extract_vitals('Blood pressure 40 over 90, pulse 96'):
    print(v['type'], v['value'], 'ishonchli:', v['plausible'])
print()
print(detect_negation('She denies chest pain but reports headache.',
                      ['chest pain','headache']))
"
```

Uchinchi qism eng muhimi: `denies` dan keyin kelgan topilma inkor qilinadi,
`but` esa doirani yopadi.

### 3.4 SOAP bo'limlarga ajratish

**Fayl:** `asr/nlp/soap.py:222`

Model emas. Har bir gap to'rt bo'limga qarshi ballanadi, eng yuqori ball
yutadi. Ishonch ball farqidan chiqadi, ya'ni ikkita bo'lim yaqin bo'lsa,
tizim buni bildiradi.

Ikki muhim tuzatish shu faylda:

- `asr/nlp/soap.py:119` — `38.0` kabi o'nlik son gapni bo'lmaydi
- `asr/nlp/soap.py:135` — Whisper pauzani vergul qilib yozganda ham bo'limlar ajraladi

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.soap import structure_note, render_sections
t = ('Patient reports headache and fever, temperature 38 degrees, '
     'blood pressure 140 over 90, impression is viral infection, '
     'plan is rest and fluids.')
for k, v in render_sections(structure_note(t)).items():
    print(k.ljust(11), v)
"
```

Diqqat qiling: matnda birorta nuqta yo'q, lekin to'rt bo'lim ham ajraldi.

### 3.5 Tashxis kodlari

**Fayl:** `asr/nlp/coding.py:137`

Til modeli emas, BM25 degan qidiruv algoritmi. Elasticsearch shu algoritmda
ishlaydi. Nega shuni tanladim:

- tashxis matni qisqa, lug'at yopiq, shunda leksik qidiruv yaxshiroq ishlaydi
- model yuklash shart emas, mikrosoniyalarda javob beradi
- qaysi so'z mos kelganini ko'rsata oladi

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.coding import suggest_codes
for c in suggest_codes('sore throat and fever, likely viral pharyngitis', 3):
    print(c['code'], round(c['confidence'],2), c['description'])
    print('   mos kelgan so\'zlar:', c['matched_terms'])
"
```

### 3.6 Shaxsiy ma'lumotlar

**Fayl:** `asr/nlp/phi.py:157`

HIPAA ro'yxatidagi identifikatorlarni topadi. spaCy bo'lsa ismlarni ham
yaxshi topadi, bo'lmasa oddiyroq usulga tushadi va buni javobda aytadi.

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.phi import detect_phi, redact
t = 'Patient Maria Gomez, MRN A4471928, phone 217-555-0143. She is 94 years old.'
d = detect_phi(t)
print('daraja:', d['risk'], '| usul:', d['ner_backend'])
for e in d['entities']: print('  ', e['type'], repr(e['text']))
print()
print(redact(t)['redacted_text'])
"
```

94 yosh ham identifikator hisoblanadi, chunki HIPAA 89 dan yuqori yoshni
alohida ko'rsatishni talab qiladi.

### 3.7 Hammasini birlashtirish

**Fayl:** `asr/nlp/pipeline.py:62`

Tartib muhim. Eng muhim bog'lanish `pipeline.py` ichida: **inkor tahlili
kodlashdan oldin ishlaydi**. Aks holda "og'riq yo'q" degan gapdan o'sha
og'riqning kodi chiqib ketardi.

**O'zingiz sinang:**

```bash
python3 -c "
from nlp.pipeline import analyze
r = analyze('Patient denies chest pain. Impression is viral infection.')
print('inkor qilingan:', r['findings']['negated'])
print('kodlashdan chiqarilgan:', r['icd10']['excluded_negated_findings'])
print('takliflar:', [c['code'] for c in r['icd10']['candidates']])
print('vaqt:', r['timings_ms']['total'], 'ms')
"
```

`R07.9` (ko'krak og'rig'i) ro'yxatda yo'qligini ko'rasiz.

---

## 4. Ma'lumot fayllari

Uchta JSON, `asr/nlp/data/` ichida. Kod emas, ma'lumot, ya'ni dasturchi bo'lmagan
odam ham to'ldirishi mumkin.

| Fayl | Nimadan iborat |
|---|---|
| `medications.json` | 118 dori, klassi va o'xshash nomlari bilan |
| `abbreviations.json` | 73 qisqartma, xavflilari alohida belgilangan |
| `icd10_subset.json` | 91 tashxis kodi, sinonimlari bilan |

Dori nomlari ikki joyda ishlatiladi: Whisper promptida va tuzatish qatlamida.
Bitta manba, shuning uchun ular hech qachon bir-biridan uzilib qolmaydi.

---

## 5. Bitta so'rov boshidan oxirigacha

```
Mikrofon
  |
  v
content.js           audio yig'adi, POST /transcribe
  |
  v
api.py:66            Whisper + klinik prompt
  |
  v
asr_quality.py       uchta ichki raqamni tekshiradi
  |
  v
content.js           transkript va ishonch chizig'ini ko'rsatadi
  |
  v  (shifokor Analyze bosadi)
api.py:211           POST /analyze
  |
  v
pipeline.py:62       soap -> vitals -> dorilar -> inkor -> kodlar -> PHI
  |
  v
field_mapper.py      qiymatlarni OpenEMR maydon nomlariga bog'laydi
  |
  v
scanner.js           sahifadan o'sha maydonlarni topadi
  |
  v
content.js           tasdiq oynasi, keyin yozadi
```

---

## 6. Kengaytma tarafi

| Fayl | Vazifasi |
|---|---|
| `extension/scanner.js` | Sahifadagi maydonlarni topadi va qanday topganini yozib qo'yadi |
| `extension/content.js` | Panel, ovoz yozish, tasdiqlash, formani to'ldirish |

Ikki muhim qoida `scanner.js` da:

- panel faqat klinik forma sahifasida chiqadi, `extension/content.js:76` da yo'l tekshiriladi
- faqat OpenEMR jadvallaridagi haqiqiy maydon nomlari qabul qilinadi,
  `extension/scanner.js:222` dagi `CLINICAL_FIELD_NAMES` ro'yxati

Shuning uchun Calendar sahifasidagi qidiruv oynasi panelni ochib yubormaydi.

---

## 7. Testlar

```bash
python3 tests/run_tests.py -v
```

51 ta test. Har biri ishlab chiqish davomida topilgan **haqiqiy xatoni**
qoplaydi. Nomlarini o'qib chiqsangiz, qanday muammolar bo'lganini ko'rasiz.

---

## 8. Rahbar so'rashi mumkin bo'lgan savollar

**"Bu yerda qanaqa AI bor?"**
Whisper nutqni tanish uchun, spaCy ismlarni topish uchun. Qolgani oddiy
algoritm. Sakkiz qatlamdan ikkitasi model.

**"Nega GPT ishlatmadingiz?"**
Tashxis kodiga sinab ko'rdim. Matn qisqa, lug'at yopiq, shunda oddiy qidiruv
algoritmi tezroq va aniqroq chiqdi. Ustiga u qaysi so'z sabab bo'lganini
ko'rsata oladi, til modeli esa ko'rsata olmaydi.

**"Modelni o'qitdingizmi?"**
Yo'q. O'qitish oylab vaqt va katta ma'lumot talab qilardi. Uning o'rniga har
so'rovda modelga klinik lug'at berdim, natija 62 dan 88 foizga chiqdi.

**"Ma'lumot qayerga boradi?"**
Hech qayerga. Whisper ham, qolgan qatlamlar ham shu kompyuterda ishlaydi.
Tarmoqqa bitta ham so'rov ketmaydi.

**"Xato qilsa nima bo'ladi?"**
Tizim o'zi yozmaydi. Ishonchi past bo'lsa, belgini o'zi yoqmaydi, shifokor
qo'lda belgilashi kerak.
