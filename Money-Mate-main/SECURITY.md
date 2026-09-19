# MoneyMate Security

ระบบเพิ่มชั้นป้องกันพื้นฐานสำหรับเว็บแอป Flask ได้แก่:

- CSRF token สำหรับคำขอ POST
- Session cookie แบบ HttpOnly และ SameSite=Lax
- Secret key สุ่มและเก็บแยกใน `.moneymate_secret`
- Rate limit สำหรับการสมัคร/เข้าสู่ระบบ (8 ครั้ง / 5 นาที / IP)
- Password hashing แบบ PBKDF2-HMAC-SHA256
- Security headers: CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy และ Permissions-Policy
- จำกัดขนาด request ที่ 5 MB ตามระบบอัปโหลดเดิม
- ปิด Flask debug mode
- Admin dashboard แสดงข้อมูลเฉพาะเมื่อ session เป็น admin

## HTTPS

ถ้านำไป deploy หลัง HTTPS ให้ตั้ง environment variable:

```bash
export MONEYMATE_SECURE_COOKIE=1
```

สำหรับการรันในเครื่องด้วย `http://localhost` ให้ใช้ค่าเริ่มต้น `0`.

> หมายเหตุ: ระบบข้อมูลการเงินเดิมยังใช้ไฟล์ JSON ร่วมกันในโปรเจกต์ ดังนั้นการแยกข้อมูลธุรกรรมรายบัญชีแบบสมบูรณ์ควรทำเป็นงานถัดไปหากจะเปิดให้หลายคนใช้งานจริงพร้อมกัน
