#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <random>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <thread>
#include <ctime>
#include <array>

// ==========================================
// 1. CONFIGURACIÓN DEL NODO (ATLACHIA)
// ==========================================
constexpr const char* FUENTE = "iot";
constexpr const char* SITIO  = "NODO-01";     // Entrada del río Atoyac en Valsequillo
constexpr double LATITUD     = 18.948;
constexpr double LONGITUD    = -98.250;

// ==========================================
// 2. CONSTANTES DEL SENSOR DFRobot SEN0237-A
// ==========================================
// Tabla oficial de saturación de oxígeno en agua (en ug/L) de 0 °C a 40 °C
constexpr std::array<double, 41> DO_TABLE_UGL = {
    14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530, // 0 - 9 °C
    11260, 11010, 10770, 10530, 10300, 10080,  9860,  9660,  9460,  9270, // 10 - 19 °C
     9080,  8900,  8730,  8570,  8410,  8250,  8110,  7960,  7820,  7690, // 20 - 29 °C
     7560,  7430,  7300,  7180,  7070,  6950,  6840,  6730,  6630,  6530, // 30 - 39 °C
     6410                                                                 // 40 °C
};

constexpr double CAL1_V_DEF = 1600.0; // Voltaje de saturación calibrado (mV)
constexpr double CAL1_T_DEF = 25.0;   // Temperatura de calibración (°C)

// ADC de 12 bits (como ESP32) a 3.3V
constexpr double ADC_VREF_MV   = 3300.0;
constexpr double ADC_MAX       = 4095.0;
constexpr double SENSOR_MAX_MV = 3000.0; // Salida máxima analógica del SEN0237-A (3.0V)
constexpr double DO_MAX_MGL    = 20.0;   // Rango máximo medible (mg/L)

// ==========================================
// 3. FUNCIONES MOLDE (REUTILIZABLES)
// ==========================================
std::string obtenerFechaISO8601() {
    auto ahora = std::chrono::system_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                  ahora.time_since_epoch()) % 1000;
    std::time_t tiempoT = std::chrono::system_clock::to_time_t(ahora);
    std::tm* utc = std::gmtime(&tiempoT);

    std::ostringstream oss;
    oss << std::put_time(utc, "%Y-%m-%dT%H:%M:%S")
        << '.' << std::setfill('0') << std::setw(3) << ms.count() << 'Z';
    return oss.str();
}

void imprimirObservacionJSON(const std::string& parametro,
                             double valor,
                             const std::string& unidad,
                             const std::string& calidad,
                             int decimales = 2) {
    std::cout << "{"
              << "\"fuente\":\"" << FUENTE << "\","
              << "\"sitio\":\"" << SITIO << "\","
              << "\"fecha\":\"" << obtenerFechaISO8601() << "\","
              << "\"parametro\":\"" << parametro << "\","
              << "\"valor\":" << std::fixed << std::setprecision(decimales) << valor << ","
              << "\"unidad\":\"" << unidad << "\","
              << "\"lat\":" << std::setprecision(4) << LATITUD << ","
              << "\"lon\":" << std::setprecision(4) << LONGITUD << ","
              << "\"calidad\":\"" << calidad << "\""
              << "}" << std::endl;
}

// ==========================================
// 4. CLASE SIMULADORA DEL SENSOR SEN0237-A
// ==========================================
class SensorDOVirtual {
private:
    double cal1_v;
    double cal1_t;

    std::mt19937 gen;
    std::normal_distribution<double> ruidoVoltaje;

    double calcularVoltajeSaturacion(double temperatura_C) const {
        return cal1_v + 35.0 * (temperatura_C - cal1_t);
    }

    int indiceTemperatura(double temperatura_C) const {
        int idx = static_cast<int>(std::round(temperatura_C));
        return std::clamp(idx, 0, 40);
    }

public:
    SensorDOVirtual(double desviacionRuidoMv = 3.0)
        : cal1_v(CAL1_V_DEF),
          cal1_t(CAL1_T_DEF),
          gen(std::random_device{}()),
          ruidoVoltaje(0.0, desviacionRuidoMv) {}

    int simularLecturaADC(double doReal_mgL, double temperatura_C) {
        doReal_mgL = std::clamp(doReal_mgL, 0.0, DO_MAX_MGL);

        int idxTemp = indiceTemperatura(temperatura_C);
        double doSat_mgL = DO_TABLE_UGL[idxTemp] / 1000.0;
        double vSat_mV = calcularVoltajeSaturacion(temperatura_C);

        double voltajeIdeal_mV = (doReal_mgL / doSat_mgL) * vSat_mV;
        double voltajeConRuido_mV = std::clamp(voltajeIdeal_mV + ruidoVoltaje(gen), 0.0, SENSOR_MAX_MV);

        int valorADC = static_cast<int>(std::round((voltajeConRuido_mV / ADC_VREF_MV) * ADC_MAX));
        return std::clamp(valorADC, 0, static_cast<int>(ADC_MAX));
    }

    double leerDO_mgL(int valorADC, double temperatura_C) const {
        double voltaje_mV = (valorADC / ADC_MAX) * ADC_VREF_MV;
        int idxTemp = indiceTemperatura(temperatura_C);
        double vSat_mV = calcularVoltajeSaturacion(temperatura_C);

        double do_ugL = (voltaje_mV * DO_TABLE_UGL[idxTemp]) / vSat_mV;
        return do_ugL / 1000.0;
    }

    // Evalúa si la lectura está dentro de los límites físicos y eléctricos de la sonda
    std::string evaluarCalidad(int valorADC, double doMedido_mgL) const {
        if (valorADC <= 0 || valorADC >= static_cast<int>(ADC_MAX)) {
            return "descartado"; // Posible desconexión de sonda o saturación del ADC
        }
        if (doMedido_mgL < 0.0 || doMedido_mgL > DO_MAX_MGL) {
            return "descartado";
        }
        return "validado";
    }

    void calibrarUnPunto(double voltajeSaturacion_mV, double temperaturaCal_C) {
        cal1_v = voltajeSaturacion_mV;
        cal1_t = temperaturaCal_C;
    }
};

// ==========================================
// 5. CONTROL DE LA SIMULACIÓN (ATLACHIA)
// ==========================================
// Segundos entre lecturas (variable INTERVALO_S; en campo serían 300 s)
int intervaloSegundos() {
    const char* v = std::getenv("INTERVALO_S");
    int s = v ? std::atoi(v) : 3;
    return s > 0 ? s : 3;
}

// Descarga simulada: el puente crea este archivo mientras el operador la tiene activa
bool descargaActiva() {
    const char* ruta = std::getenv("EVENTO_ARCHIVO");
    std::ifstream f(ruta ? ruta : "/tmp/atlachia_descarga");
    return f.good();
}

int main() {
    SensorDOVirtual sensor(3.0);
    const int INTERVALO_SEGUNDOS = intervaloSegundos();
    double tiempoSimulado = 0.0;

    while (true) {
        // Temperatura de referencia desacoplada (20 °C, acorde a Valsequillo)
        double tempCompensacion_C = 20.0;

        // Simula oxígeno disuelto en la presa (entre 4.5 y 7.5 mg/L)
        double doReal_mgL = 6.0 + 1.5 * std::sin(tiempoSimulado * 0.12);
        if (descargaActiva()) doReal_mgL -= 3.0;      // descarga: la materia orgánica consume oxígeno

        int adc = sensor.simularLecturaADC(doReal_mgL, tempCompensacion_C);
        double doMedido_mgL = sensor.leerDO_mgL(adc, tempCompensacion_C);
        std::string calidad = sensor.evaluarCalidad(adc, doMedido_mgL);

        // Emite el JSON exactamente con el contrato de Atlachia
        imprimirObservacionJSON("oxigeno_disuelto", doMedido_mgL, "mg/L", calidad, 2);

        tiempoSimulado += INTERVALO_SEGUNDOS;
        std::this_thread::sleep_for(std::chrono::seconds(INTERVALO_SEGUNDOS));
    }

    return 0;
}