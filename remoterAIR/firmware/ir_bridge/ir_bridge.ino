/*
 * RemoteAIR — IR Bridge Firmware v1.0.0
 * ESP8266 (NodeMCU / Wemos D1 Mini)
 *
 * Wiring:
 *   IR Receiver  → D5 (GPIO14)
 *   IR Emitter   → D2 (GPIO4)  [via 2N2222 transistor + 100Ω resistor]
 *   DHT22 Sensor → D6 (GPIO12) [optional]
 *
 * Libraries (Arduino Library Manager):
 *   - IRremoteESP8266 by David Conran
 *   - ESPAsyncWebServer by dvarrel
 *   - ESPAsyncTCP by dvarrel
 *   - ArduinoJson by Benoit Blanchon
 *   - DHT sensor library by Adafruit [optional]
 */

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <IRremoteESP8266.h>
#include <IRrecv.h>
#include <IRsend.h>
#include <IRutils.h>
#include <LittleFS.h>
#include <ESP8266mDNS.h>

// ============================================================
//  Pins
// ============================================================
const uint16_t IR_RECV_PIN = 14; // D5
const uint16_t IR_SEND_PIN = 4;  // D2

// ============================================================
//  Constants
// ============================================================
const char* AP_SSID     = "RemoteAIR-Setup";
const char* AP_PASSWORD = "12345678";
const char* FIRMWARE_VERSION = "1.0.0";
const char* CONFIG_FILE = "/config.json";
const uint16_t CAPTURE_BUF = 1024;
const uint8_t  LEARN_TIMEOUT_SEC = 12;

// ============================================================
//  Globals
// ============================================================
AsyncWebServer server(80);
IRrecv irrecv(IR_RECV_PIN, CAPTURE_BUF, 50, true);
IRsend irsend(IR_SEND_PIN);
decode_results irResults;

bool isLearning = false;
bool learnSuccess = false;
String learnedSignal = "";
String learnedProtocol = "";
uint16_t learnedBits = 0;
unsigned long learnStartMs = 0;

String configSsid = "";
String configPass = "";
bool apMode = false;

// ============================================================
//  Config helpers
// ============================================================
bool loadConfig() {
  if (!LittleFS.exists(CONFIG_FILE)) return false;
  File f = LittleFS.open(CONFIG_FILE, "r");
  if (!f) return false;
  DynamicJsonDocument doc(256);
  if (deserializeJson(doc, f)) { f.close(); return false; }
  f.close();
  configSsid = doc["ssid"] | "";
  configPass = doc["pass"] | "";
  return configSsid.length() > 0;
}

void saveConfig(const String& ssid, const String& pass) {
  DynamicJsonDocument doc(256);
  doc["ssid"] = ssid;
  doc["pass"] = pass;
  File f = LittleFS.open(CONFIG_FILE, "w");
  serializeJson(doc, f);
  f.close();
}

// ============================================================
//  WiFi setup
// ============================================================
void startAP() {
  apMode = true;
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.println("[AP] Started: " + String(AP_SSID));
  Serial.println("[AP] IP: " + WiFi.softAPIP().toString());
}

bool connectSTA(const String& ssid, const String& pass, unsigned long timeoutMs = 15000) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), pass.c_str());
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());
    apMode = false;
    return true;
  }
  Serial.println("\n[WiFi] Failed");
  return false;
}

// ============================================================
//  CORS helper
// ============================================================
void addCORS(AsyncWebServerResponse* res) {
  res->addHeader("Access-Control-Allow-Origin", "*");
  res->addHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res->addHeader("Access-Control-Allow-Headers", "Content-Type");
}

AsyncWebServerResponse* jsonResp(AsyncWebServerRequest* req, const String& body, int code = 200) {
  auto* res = req->beginResponse(code, "application/json", body);
  addCORS(res);
  return res;
}

// ============================================================
//  API routes
// ============================================================
void setupRoutes() {
  // OPTIONS preflight
  server.onNotFound([](AsyncWebServerRequest* req) {
    if (req->method() == HTTP_OPTIONS) {
      auto* r = req->beginResponse(200);
      addCORS(r);
      req->send(r);
    } else {
      req->send(jsonResp(req, "{\"error\":\"not found\"}", 404));
    }
  });

  // GET /api/status
  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* req) {
    DynamicJsonDocument doc(256);
    doc["online"]   = true;
    doc["firmware"] = FIRMWARE_VERSION;
    doc["freeHeap"] = ESP.getFreeHeap();
    if (!apMode) {
      doc["ssid"] = WiFi.SSID();
      doc["rssi"] = WiFi.RSSI();
      doc["ip"]   = WiFi.localIP().toString();
    }
    String out;
    serializeJson(doc, out);
    req->send(jsonResp(req, out));
  });

  // POST /api/learn  — waits up to LEARN_TIMEOUT_SEC for IR signal
  server.on("/api/learn", HTTP_POST, [](AsyncWebServerRequest* req) {
    if (isLearning) {
      req->send(jsonResp(req, "{\"error\":\"already learning\"}", 409));
      return;
    }
    isLearning    = true;
    learnSuccess  = false;
    learnedSignal = "";
    learnStartMs  = millis();
    irrecv.enableIRIn();

    // Blocking wait (async server handles one req at a time here)
    unsigned long deadline = millis() + LEARN_TIMEOUT_SEC * 1000UL;
    while (millis() < deadline) {
      if (irrecv.decode(&irResults)) {
        if (irResults.decode_type != UNKNOWN) {
          learnedSignal   = resultToHexidecimal(&irResults);
          learnedProtocol = typeToString(irResults.decode_type);
          learnedBits     = irResults.bits;
          learnSuccess    = true;
        }
        irrecv.resume();
        break;
      }
      delay(5);
      ESP.wdtFeed();
    }
    irrecv.disableIRIn();
    isLearning = false;

    DynamicJsonDocument doc(512);
    if (learnSuccess) {
      doc["success"]  = true;
      doc["signal"]   = learnedSignal;
      doc["protocol"] = learnedProtocol;
      doc["bits"]     = learnedBits;
    } else {
      doc["success"] = false;
      doc["error"]   = "timeout — no signal received";
    }
    String out;
    serializeJson(doc, out);
    req->send(jsonResp(req, out));
  });

  // POST /api/send  body: {"signal":"0xABCD..."}
  server.on("/api/send", HTTP_POST, [](AsyncWebServerRequest* req) {},
    nullptr,
    [](AsyncWebServerRequest* req, uint8_t* data, size_t len, size_t, size_t) {
      DynamicJsonDocument doc(512);
      if (deserializeJson(doc, data, len)) {
        req->send(jsonResp(req, "{\"error\":\"invalid JSON\"}", 400));
        return;
      }
      String signal = doc["signal"] | "";
      if (signal.length() == 0) {
        req->send(jsonResp(req, "{\"error\":\"missing signal\"}", 400));
        return;
      }
      // Parse hex string to uint16_t array (raw timing)
      // For NEC / standard protocols decode and send with type
      // Simplified: always send as raw hex via sendRaw workaround
      // For real AC codes use IRac class from IRremoteESP8266
      irsend.sendNEC(strtoul(signal.c_str(), nullptr, 16));
      req->send(jsonResp(req, "{\"success\":true}"));
    }
  );

  // GET /api/wifi/scan
  server.on("/api/wifi/scan", HTTP_GET, [](AsyncWebServerRequest* req) {
    int n = WiFi.scanNetworks();
    DynamicJsonDocument doc(1024);
    JsonArray arr = doc.createNestedArray("networks");
    for (int i = 0; i < n; i++) {
      JsonObject net = arr.createNestedObject();
      net["ssid"] = WiFi.SSID(i);
      net["rssi"] = WiFi.RSSI(i);
      net["enc"]  = WiFi.encryptionType(i) != ENC_TYPE_NONE;
    }
    String out;
    serializeJson(doc, out);
    req->send(jsonResp(req, out));
  });

  // POST /api/wifi/connect  body: {"ssid":"...","password":"..."}
  server.on("/api/wifi/connect", HTTP_POST, [](AsyncWebServerRequest* req) {},
    nullptr,
    [](AsyncWebServerRequest* req, uint8_t* data, size_t len, size_t, size_t) {
      DynamicJsonDocument doc(256);
      if (deserializeJson(doc, data, len)) {
        req->send(jsonResp(req, "{\"error\":\"invalid JSON\"}", 400));
        return;
      }
      String ssid = doc["ssid"] | "";
      String pass = doc["password"] | "";
      if (ssid.length() == 0) {
        req->send(jsonResp(req, "{\"error\":\"missing ssid\"}", 400));
        return;
      }
      saveConfig(ssid, pass);
      req->send(jsonResp(req, "{\"success\":true,\"message\":\"restarting\"}"));
      delay(500);
      ESP.restart();
    }
  );

  // GET /api/reset — factory reset
  server.on("/api/reset", HTTP_GET, [](AsyncWebServerRequest* req) {
    LittleFS.remove(CONFIG_FILE);
    req->send(jsonResp(req, "{\"success\":true,\"message\":\"factory reset, restarting\"}"));
    delay(500);
    ESP.restart();
  });
}

// ============================================================
//  Setup
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== RemoteAIR IR Bridge " + String(FIRMWARE_VERSION) + " ===");

  LittleFS.begin();
  irsend.begin();

  if (loadConfig()) {
    Serial.println("[WiFi] Connecting to: " + configSsid);
    if (!connectSTA(configSsid, configPass)) {
      Serial.println("[WiFi] Falling back to AP mode");
      startAP();
    }
  } else {
    Serial.println("[WiFi] No config — AP mode");
    startAP();
  }

  if (!apMode && MDNS.begin("remoteair")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("[mDNS] remoteair.local");
  }

  setupRoutes();
  server.begin();
  Serial.println("[HTTP] Server started");
}

// ============================================================
//  Loop
// ============================================================
void loop() {
  if (!apMode) MDNS.update();
  delay(10);
}
