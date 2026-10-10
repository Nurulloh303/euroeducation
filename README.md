# EURO EDUCATION

Sayt + serverda ishlaydigan admin panel (Flask + SQLite).

## Ishga tushirish

Python 3.10+ kerak.

```bash
pip install -r requirements.txt
export ADMIN_PASSWORD='KUCHLI_MAXFIY_PAROL'  # Windows PowerShell: $env:ADMIN_PASSWORD='...'
export SECRET_KEY='UZUN_TASODIFIY_SECRET'  # Windows PowerShell: $env:SECRET_KEY='...'
python app.py
```

Sayt: http://localhost:5000
Admin: http://localhost:5000/admin
Login: `admin`, parol `ADMIN_PASSWORD`. Agar parol birinchi ishga tushirishda belgilanmagan bo‘lsa, terminalda yaratilgan parol chiqadi. Keyingi ishga tushirishlarda mavjud admin paroli saqlanadi.

Admin orqali ustoz rasmi, fani, bio va o‘quv rejalarini (PDF, DOCX, PPTX fayllari bilan) qo‘shish/tahrirlash/o‘chirish mumkin. Ma’lumotlar `data.sqlite3`da, rasmlar va yuklangan hujjatlar `static/uploads/`da saqlanadi. Ikkalasini zaxiralang.

## Internetga joylash

Python/Flask ishlaydigan hosting kerak (masalan VPS yoki persistent diskli PaaS). Start command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`. HTTPS, `SECRET_KEY`, `ADMIN_PASSWORD`, persistent storage va backupni sozlang. Oddiy static hosting (Netlify drag-and-drop) admin ma’lumotlarini saqlay olmaydi. CRM o‘quvchi hisoblari va EURO COIN balansi ushbu loyihada ulanmagan: sayt CRM imkoniyatlarini tavsiflaydi, lekin haqiqiy o‘quvchi ma’lumotlarini ko‘rsatmaydi.

## Eslatma

Logo foydalanuvchi yuborgan EURO SCHOOL logotipidagi belgiga asoslangan va EURO EDUCATION yozuviga moslangan. Agar rasmiy vektor logotip bo‘lsa, `static/logo.png`ni almashtirish mumkin.
