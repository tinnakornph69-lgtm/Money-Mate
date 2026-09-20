# ตั้งค่า MoneyMate บน Render ให้ข้อมูลไม่หาย

โค้ดชุดนี้ใช้ไฟล์ JSON เมื่อรันในเครื่อง และเปลี่ยนไปใช้ PostgreSQL อัตโนมัติเมื่อมีตัวแปร `DATABASE_URL`

## ตั้งค่า Web Service

- Root Directory: เว้นว่าง (ไฟล์ `app.py` ต้องอยู่ที่รากของ repository)
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn wsgi:app`

## ตั้งค่าฐานข้อมูลถาวร

1. สร้าง PostgreSQL database ใน Render หรือผู้ให้บริการ PostgreSQL ที่ใช้งานอยู่
2. เปิด Web Service > Environment
3. เพิ่ม `DATABASE_URL` เป็น Internal Database URL/Connection URL ของฐานข้อมูล
4. เพิ่ม `SECRET_KEY` เป็นข้อความสุ่มยาวอย่างน้อย 32 ตัวอักษร แล้วเก็บค่าเดิมไว้ตลอด
5. เพิ่ม `MONEYMATE_SECURE_COOKIE` เป็น `1` สำหรับเว็บไซต์ HTTPS บน Render
6. กด Save Changes แล้ว Deploy latest commit

ตาราง `moneymate_storage` จะถูกสร้างอัตโนมัติในการเปิดเว็บครั้งแรก ข้อมูลบัญชี รายรับรายจ่าย งบประมาณ เป้าหมายออม และรายรับประจำจะอยู่ในฐานข้อมูลและไม่หายเมื่อดีพลอยใหม่

ไฟล์ `app.py`, `storage.py` และ `templates/base.html` ยังคงตรงกับไฟล์ต้นฉบับของรายวิชา ระบบเพิ่มเติมอยู่ใน `wsgi.py`, `moneymate_bootstrap.py`, `persistent_store.py` และ `templates/_money_base.html`

> สำคัญ: ถ้าไม่ตั้ง `DATABASE_URL` เว็บยังรันได้ แต่จะใช้ JSON ในเครื่องเซิร์ฟเวอร์และข้อมูลอาจหายเมื่อ Render เปลี่ยน instance
