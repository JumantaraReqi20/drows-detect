#include <Arduino.h>

// WiFi stuff
#include <WiFi.h>
#include <WebServer.h>
#include <WiFiClient.h>

// OTA stuff
#include <ESPmDNS.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>

// Camera stuff
#include "OV2640.h"
#include "OV2640Streamer.h"
#include "CRtspSession.h"

// Button stuff
#include <OneButton.h>

// --- KONFIGURASI PENTING ---
// Kita butuh keduanya: RTSP untuk stream video ke Python,
// WebServer untuk menerima perintah /flash_on dari Python.
#define ENABLE_WEBSERVER 
#define ENABLE_RTSPSERVER

// Camera class
extern OV2640 cam;

// RTSP stuff
void initRTSP(void);
void stopRTSP(void);

// Web server stuff
void initWebStream(void);
void stopWebStream(void);
// void handleWebServer(void); // Tidak dipakai di task loop

// OTA stuff
void startOTA(void);
void stopOTA(void);
extern boolean otaStarted;

// Definisi Pin Flash (LED Built-in)
#define FLASH_LED_PIN 4