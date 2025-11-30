// WIFI credentials
// #define THUIS
#define E109

#ifdef THUIS
    #define SECRET_SSID "Proximus-Home-2110"
    #define SECRET_PASS "mU4q2pVq2CZ1"
    #define serverIP "192.168.1.35" // HTTP Server
    #define serverPort 5050         // HTTP Poort server
#endif

#ifdef E109
    #define SECRET_SSID "E109-E110"
    #define SECRET_PASS "DBHaacht24"
    #define serverIP "192.168.0.35" // HTTP Server
    #define serverPort 5050         // HTTP Poort server
#endif