#include "main.h"

/** Masukkan kredensial WiFi di file ini **/
#include "wifikeys.h"

/** Camera class */
OV2640 cam;

/** GPIO for OTA request button */
int otaButton = 12;
/** Button class */
OneButton pushBt(otaButton, true, true);

/** Function declarations */
void enableOTA(void);
void resetDevice(void);

void setup()
{
  // Setup Pin Flash sebagai Output & Pastikan Mati di awal
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW); 
  
  // Debugging LED (Merah di belakang)
  pinMode(33, OUTPUT); // LED Builtin merah biasanya pin 33
  digitalWrite(33, HIGH); // HIGH = Mati (Logic terbalik)

  Serial.begin(115200);
  Serial.println("\n\n##################################");
  Serial.println("Starting System...");

  // Initialize ESP32 CAM
  // Gunakan config default Aithinker
  cam.init(esp32cam_aithinker_config);
  delay(100);

  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    // --- PENTING UNTUK PROJECT ANDA ---
    // Gunakan QVGA agar FPS tinggi dan latency rendah untuk diproses Python
    s->set_framesize(s, FRAMESIZE_QVGA); 
    
    // Quality: 10-63 (Makin kecil makin bagus gambarnya, tapi makin berat datanya)
    // Gunakan 12-15 agar seimbang.
    s->set_quality(s, 15);
  }

  // Connect WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  IPAddress ip = WiFi.localIP();
  Serial.print("\nWiFi connected with IP ");
  Serial.println(ip);

#ifdef ENABLE_RTSPSERVER
  Serial.print("RTSP Stream Link: rtsp://");
  Serial.print(ip);
  Serial.println(":8554/mjpeg/1\n");
  initRTSP(); // Mulai RTSP Task
#endif

#ifdef ENABLE_WEBSERVER
  Serial.print("HTTP Command Link: http://");
  Serial.print(ip);
  Serial.println("/flash_on\n");
  initWebStream(); // Mulai WebServer Task
#endif

  // Attach button functions
  pushBt.attachClick(enableOTA);
  pushBt.attachDoubleClick(resetDevice);
}

void loop()
{
  // Check button for OTA
  pushBt.tick();
  
  if (otaStarted)
  {
    ArduinoOTA.handle();
  }

  // Loop kosong karena semua dijalankan di Task (FreeRTOS)
  delay(100);
}

/** Handle button single click - Masuk Mode OTA */
void enableOTA(void)
{
  if (!otaStarted)
  {
#ifdef ENABLE_WEBSERVER
    stopWebStream();
#endif
#ifdef ENABLE_RTSPSERVER
    stopRTSP();
#endif
    delay(100);
    Serial.println("OTA enabled");
    startOTA();
    otaStarted = true;
  }
  else
  {
    otaStarted = false;
    stopOTA();
    // Restart logic (sebaiknya restart device sih biar fresh)
    esp_restart();
  }
}

/** Handle button double click - Reset */
void resetDevice(void)
{
  delay(100);
  WiFi.disconnect();
  esp_restart();
}