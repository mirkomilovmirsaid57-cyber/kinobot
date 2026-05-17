# 🎬 KinoBot — Render.com da tekin deploy qilish

## 📋 Qadamlar

### 1. GitHub'ga yuklash
1. https://github.com ga kiring
2. **New repository** → nom bering (masalan: `kinobot`)
3. Barcha fayllarni yuklang

### 2. Render.com da baza yaratish
1. https://render.com ga kiring (Google bilan)
2. **New** → **PostgreSQL** bosing
3. Quyidagilarni kiriting:
   - Name: `kinobot-db`
   - Plan: **Free**
4. **Create Database** bosing
5. Ko'rsatilgan **External Database URL** ni nusxalab oling

### 3. config.py ni yangilash
`DATABASE_URL` ga nusxalangan URL ni joylashtiring

### 4. Render.com da bot yaratish
1. **New** → **Web Service** bosing
2. GitHub repo'ni ulang
3. Quyidagilarni kiriting:
   - Name: `kinobot`
   - Runtime: **Python**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Plan: **Free**
4. **Create Web Service** bosing

---

## 📌 Bot buyruqlari

**Foydalanuvchilar:**
- `/start` — Boshlash
- `/kinolar` — Bepul kinolar
- `/premium` — Premium kinolar
- `K1001` — Kod orqali kino olish

**Admin (@CineRotaMix_vip):**
- `/addmovie Nom | Yil | Janr | Reyting | Tavsif | premium/free`
- `/delmovie K1001`
- `/givesub 123456789 30`
- `/users`

---

## 🎬 Kino qo'shish misoli
```
/addmovie Interstellar | 2014 | Sci-Fi | 8.6 | Kosmik film | premium
```
Bot avtomatik `K0001` kabi kod beradi.

---

## ⚠️ Muhim
Render.com tekin plan 15 daqiqa faolsiz bo'lsa "uxlab qoladi". 
Doim ishlashi uchun **UptimeRobot.com** da tekin monitor qo'shing.
