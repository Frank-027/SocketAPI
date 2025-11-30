// ESP32 Client die data van BMP280 sensor leest en naar server stuurt in JSON formaat
// Gebaseerd op Arduino framework en gebruikt WiFiClient voor socket communicatie
//
// Bibliotheken: WiFi, Adafruit BMP280, ArduinoJson
//
// BMP280 sensor is aangesloten via I2C (SDA op GPIO 21, SCL op GPIO 22)
// Let op bmp280 adres voor I2C adres = 0x76 of 0x77 afhankelijk van de module
//
// Auteur: Frank Demonie
// Datum:  2024-06-15

#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <ArduinoJson.h>
#include <Secrets.h>

#define DEBUG 1 // commentaar uit voor geen debug info  

#define HEADER 64 //zelfde als server
#define MAX_RETRYS 5
#define BMP280_ADDRESS 0x76
#define SEALEVELPRESSURE_HPA (1013.25)  
#define JSON_BUFFER_SIZE 200
#define TIME_BETWEEN_MEASUREMENTS 5000 // in ms
#define MONITOR_BAUDRATE 115200

WiFiClient client;
Adafruit_BMP280 bmp; // I2C instance

// Functie declaraties
void connectToServer();

void setup() {
    Serial.begin(MONITOR_BAUDRATE );
    delay(1000);

    // Verbinden met WiFi
    Serial.println("Verbinden met WiFi...");
    WiFi.begin( SECRET_SSID, SECRET_PASS );
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("WiFi verbonden! IP adres: %s\n", WiFi.localIP().toString().c_str() );
 
    // Initialiseer BMP280 sensor
    if (!bmp.begin( BMP280_ADDRESS )) {
        Serial.println("Kan BMP280 sensor niet vinden! Controleer de verbinding.");
        while (1) delay( 10 );
    }
    Serial.println("BMP280 sensor gevonden!");

    // Verbinden met server
    connectToServer();
}

void loop() {
    float temperature = bmp.readTemperature();
    float pressure = bmp.readPressure() / 100.0F; // hPa
    float altitude = bmp.readAltitude(SEALEVELPRESSURE_HPA);

    // JSON maken
    StaticJsonDocument< JSON_BUFFER_SIZE > doc;
    doc["temperature"] = temperature;
    doc["pressure"] = pressure;
    doc["altitude"] = altitude; 
    String jsonStr;
    serializeJson(doc, jsonStr);
    

    // Herconnectie met server indien nodig
    int retrys = 0;
    while ( !client.connected() && retrys <= MAX_RETRYS ) {
        Serial.printf("Niet verbonden, probeer opnieuw te verbinden...%d\n", retrys+1);
        client.stop();
        connectToServer();
        retrys++;
        delay(1000);
    }

    // Bericht sturen indien verbonden
    if ( client.connected() ) {
        #ifdef DEBUG
            Serial.println("Verbonden met server!");
        #endif
    
        // Verstuur de lengte van het bericht eerst, zoals server verwacht
        String lenStr = String(jsonStr.length());
        while (lenStr.length() < HEADER) {
            lenStr += " "; // vul aan tot HEADER lengte
        }    
        client.print(lenStr);
        delay(10); // korte pauze
        client.print( jsonStr );    

        // Wacht op antwoord van server
        while (client.available() == 0) {
            delay(10);
        }
        String response = client.readString();
        if ( response.startsWith("ACK") ) {
            Serial.println("Server bevestigde ontvangst van data.");
            Serial.printf("Verstuur JSON: %s\n", jsonStr.c_str());
        } else {
            Serial.println("Onverwacht antwoord van server.");
        }
    } else {
        Serial.println("Kan niet verbinden met server");
    }

    delay( 5000 ); // 5 seconden wachten voor volgende meting
}

void connectToServer() {
    Serial.println("Verbind met server...");
    if (client.connect(serverIP, serverPort)) {
        Serial.println("Verbonden met server!");
    } else {
        Serial.println("Kan niet verbinden met server. Probeer later opnieuw...");
    }
}