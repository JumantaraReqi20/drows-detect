#include "main.h"

/** Web server class */
WebServer server(80);

/** Forward declaration */
void webTask(void *pvParameters);
TaskHandle_t webTaskHandler;
boolean stopWeb = false;

// --- FUNGSI BARU UNTUK FLASH ---
void handle_flash_on();
void handle_flash_off();

// Fungsi bawaan lama
void handle_jpg_stream(void); // Kita biarkan ada, tapi mungkin tidak dipakai
void handle_jpg(void);
void handleNotFound();

void initWebStream(void)
{
#ifdef ENABLE_WEBSERVER
  xTaskCreate(webTask, "WEB", 4096, NULL, 1, &webTaskHandler);
#endif
}

void stopWebStream(void)
{
  stopWeb = true;
}

void webTask(void *pvParameters)
{
  // --- DAFTARKAN URL DI SINI ---
  
  // 1. URL untuk Kontrol Flash (Dipanggil oleh Python)
  server.on("/flash_on", HTTP_GET, handle_flash_on);
  server.on("/flash_off", HTTP_GET, handle_flash_off);

  // 2. URL Bawaan (Opsional, buat cek kamera via browser)
  server.on("/", HTTP_GET, handle_jpg_stream);
  server.on("/jpg", HTTP_GET, handle_jpg);
  server.onNotFound(handleNotFound);

  server.begin();
  
  while (1)
  {
    if (stopWeb) {
      server.close();
      vTaskDelete(NULL);
    }
    
    // Handle request dari Python
    server.handleClient();
    
    // Beri jeda sedikit agar tidak makan CPU resource RTSP
    delay(10); 
  }
}

// --- IMPLEMENTASI LOGIKA FLASH ---

void handle_flash_on()
{
  digitalWrite(FLASH_LED_PIN, HIGH); // Nyalakan Lampu (GPIO 4)
  server.send(200, "text/plain", "Flash ON");
  Serial.println("CMD: Flash ON");
}

void handle_flash_off()
{
  digitalWrite(FLASH_LED_PIN, LOW); // Matikan Lampu (GPIO 4)
  server.send(200, "text/plain", "Flash OFF");
  Serial.println("CMD: Flash OFF");
}

// --- IMPLEMENTASI STREAMING BAWAAN (JANGAN DIHAPUS BIAR GAK ERROR) ---

void handle_jpg_stream(void)
{
  WiFiClient thisClient = server.client();
  String response = "HTTP/1.1 200 OK\r\n";
  response += "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n";
  server.sendContent(response);

  while (1)
  {
    cam.run();
    if (!thisClient.connected()) break;
    
    response = "--frame\r\n";
    response += "Content-Type: image/jpeg\r\n\r\n";
    server.sendContent(response);

    thisClient.write((char *)cam.getfb(), cam.getSize());
    server.sendContent("\r\n");
    delay(150);
  }
}

void handle_jpg(void)
{
  WiFiClient thisClient = server.client();
  cam.run();
  if (!thisClient.connected()) return;
  
  String response = "HTTP/1.1 200 OK\r\n";
  response += "Content-disposition: inline; filename=capture.jpg\r\n";
  response += "Content-type: image/jpeg\r\n\r\n";
  server.sendContent(response);
  thisClient.write((char *)cam.getfb(), cam.getSize());
}

void handleNotFound()
{
  server.send(404, "text/plain", "Not Found");
}