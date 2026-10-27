# RemoteAIR — รีโมทแอร์บ้าน โดย ลุงพี

แอปมือถือ (Android / iOS) สำหรับควบคุมแอร์บ้านผ่าน IR Bridge ESP8266

---

## คุณสมบัติ

| คุณสมบัติ | รายละเอียด |
|---|---|
| 📡 สแกนสัญญาณ IR | รับสัญญาณจากรีโมทเดิม บันทึกชื่อได้ |
| 🏠 หลายเครื่อง | เพิ่มแอร์ได้ไม่จำกัด ตั้งชื่อ/ตำแหน่งเอง |
| 🌡 ปรับอุณหภูมิ | 16–30 °C ผ่าน UI หรือ slider |
| ⏱ ตั้งเวลา | เปิด/ปิดอัตโนมัติ เลือกวัน/เวลา/โหมด |
| 📊 ประสิทธิภาพ | อุณหภูมิห้อง, ความชื้น, RSSI, พลังงาน |
| 📲 QR ติดตั้ง | สร้าง QR ส่งให้ผู้ใช้ได้เลย |

---

## โครงสร้างโปรเจกต์

```
remoterAIR/
├── app/                  # Flutter mobile app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── theme.dart
│   │   ├── models/       # AcDevice, TimerSchedule
│   │   ├── providers/    # AcProvider (state management)
│   │   ├── services/     # BridgeService, StorageService
│   │   └── screens/      # home, control, scan, timer, performance
│   └── pubspec.yaml
├── firmware/
│   └── ir_bridge/
│       └── ir_bridge.ino  # ESP8266 Arduino firmware
├── generate_qr.py         # สร้าง QR code
├── VERSION.json
└── CHANGELOG.md
```

---

## ฮาร์ดแวร์ IR Bridge

### อุปกรณ์
- ESP8266 (NodeMCU v3 หรือ Wemos D1 Mini)
- IR Receiver TSOP38238 หรือ VS1838B
- IR LED 940nm + ทรานซิสเตอร์ 2N2222 + ตัวต้านทาน 100Ω
- [ไม่บังคับ] DHT22 วัดอุณหภูมิ/ความชื้นห้อง

### วงจร
```
IR Receiver  → D5 (GPIO14)
IR Emitter   → D2 (GPIO4)  [ผ่าน 2N2222 + R 100Ω]
DHT22        → D6 (GPIO12) [optional]
```

### อัพโหลด Firmware
1. เปิด Arduino IDE
2. ติดตั้ง libraries: IRremoteESP8266, ESPAsyncWebServer, ArduinoJson, LittleFS
3. เลือก Board: NodeMCU 1.0 (ESP-12E Module)
4. อัพโหลด `firmware/ir_bridge/ir_bridge.ino`

---

## การตั้งค่าครั้งแรก

1. **ESP8266 สร้าง Hotspot** ชื่อ `RemoteAIR-Setup` รหัส `12345678`
2. **เชื่อมต่อโทรศัพท์** เข้า WiFi นั้น
3. **เปิดแอป** → เพิ่มแอร์ → IP: `192.168.4.1`
4. **ในแอปกด** "สแกนหา Bridge" เพื่อหา IP อัตโนมัติ
5. หลังบันทึก WiFi บ้าน → ESP8266 restart แล้วต่อ WiFi บ้านอัตโนมัติ

---

## สร้างและรัน Flutter App

```bash
cd app
flutter pub get
flutter run                    # รันบนอุปกรณ์ที่เชื่อมต่อ
flutter build apk --release    # สร้าง APK สำหรับ Android
flutter build ios --release    # สร้างสำหรับ iOS (ต้องใช้ Mac + Xcode)
```

---

## สร้าง QR Code

```bash
pip install qrcode[pil] Pillow
python generate_qr.py                        # QR link ดาวน์โหลด APK
python generate_qr.py --url https://your-url --out ./qr
python generate_qr.py --all                  # ทุกแบบ (APK, Play, AppStore, Source)
```

---

## API ของ IR Bridge

| Method | Path | รายละเอียด |
|---|---|---|
| GET | /api/status | สถานะ, WiFi RSSI, อุณหภูมิ |
| POST | /api/learn | รอสัญญาณ IR (timeout 12 วิ) |
| POST | /api/send | ส่งสัญญาณ IR `{"signal":"0x..."}` |
| GET | /api/wifi/scan | สแกน WiFi |
| POST | /api/wifi/connect | บันทึก WiFi `{"ssid":"...","password":"..."}` |
| GET | /api/reset | Factory reset |

---

## Version
ดูที่ [VERSION.json](VERSION.json) และ [CHANGELOG.md](CHANGELOG.md)
