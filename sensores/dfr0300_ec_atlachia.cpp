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

// ==========================================
// 1. CONFIGURACIÓN DEL NODO (ATLACHIA)
// ==========================================
constexpr const char* FUENTE = "iot";
constexpr const char* SITIO  = "NODO-01";     // Entrada del río Atoyac en Valsequillo
constexpr double LATITUD     = 18.948;
constexpr double LONGITUD    = -98.250;

// ==========================================
// 2. CONSTANTES DEL SENSOR DFR0300 (K=1)
// ==========================================
constexpr double RES2       = 820.0;
constexpr double ECREF      = 200.0;
constexpr double TEMP_REF   = 25.0;
constexpr double TEMP_COEFF = 0.0185;

// ADC de 12 bits (como ESP32) a 3.3V
constexpr double ADC_VREF_MV   = 3300.0;
constexpr double ADC_MAX       = 4095.0;
constexpr double SENSOR_MAX_MV = 3400.0;
constexpr double EC_MAX_MSCM   = 20.0;        // Rango máximo del DFR0300 K=1

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
                             int decimales = 3) {
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
// 4. CLASE SIMULADORA DEL SENSOR DFR0300
// ==========================================
class SensorECVirtual {
private:
    double kvalue     = 1.0;
    double kvalueLow  = 1.0;
    double kvalueHigh = 1.0;

    std::mt19937 gen;
    std::normal_distribution<double> ruidoVoltaje;

public:
    SensorECVirtual(double desviacionRuidoMv = 2.5)
        : gen(std::random_device{}()),
          ruidoVoltaje(0.0, desviacionRuidoMv) {}

    int simularLecturaADC(double ecReal_mScm, double temperatura_C) {
        double ecConTemp = ecReal_mScm * (1.0 + TEMP_COEFF * (temperatura_C - TEMP_REF));
        double voltaje_mV = (ecConTemp * RES2 * ECREF) / 1000.0;

        voltaje_mV += ruidoVoltaje(gen);
        double limite = std::min(SENSOR_MAX_MV, ADC_VREF_MV);
        voltaje_mV = std::clamp(voltaje_mV, 0.0, limite);

        int adc = static_cast<int>(std::round((voltaje_mV / ADC_VREF_MV) * ADC_MAX));
        return std::clamp(adc, 0, static_cast<int>(ADC_MAX));
    }

    double leerEC(int valorADC, double temperatura_C) {
        double voltaje_mV = (valorADC / ADC_MAX) * ADC_VREF_MV;
        double rawEC = (1000.0 * voltaje_mV) / RES2 / ECREF;

        double valueTemp = rawEC * kvalue;
        if (valueTemp > 2.5) {
            kvalue = kvalueHigh;
        } else if (valueTemp < 2.0) {
            kvalue = kvalueLow;
        }

        double ecSinCompensar = rawEC * kvalue;
        return ecSinCompensar / (1.0 + TEMP_COEFF * (temperatura_C - TEMP_REF));
    }

    // Evalúa si la lectura está dentro de los límites físicos del sensor y sin saturación
    std::string evaluarCalidad(int valorADC, double ecMedido) const {
        if (valorADC <= 0 || valorADC >= static_cast<int>(ADC_MAX)) {
            return "descartado"; // Posible desconexión o saturación del ADC
        }
        if (ecMedido < 0.0 || ecMedido > EC_MAX_MSCM) {
            return "descartado";
        }
        return "validado";
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
    SensorECVirtual sensor(2.5);
    const int INTERVALO_SEGUNDOS = intervaloSegundos();
    double tiempoSimulado = 0.0;

    while (true) {
        // Como este módulo corre aislado por ahora, usamos 20 °C de referencia (acorde a Valsequillo)
        double tempCompensacion_C = 20.0;

        // Simula conductividad típica de agua superficial con carga orgánica/sales (0.8 a 1.6 mS/cm)
        double ecReal = 1.2 + 0.4 * std::sin(tiempoSimulado * 0.12);
        if (descargaActiva()) ecReal += 0.6;          // descarga: más sales y residuos disueltos

        int adc = sensor.simularLecturaADC(ecReal, tempCompensacion_C);
        double ecMedido = sensor.leerEC(adc, tempCompensacion_C);
        std::string calidad = sensor.evaluarCalidad(adc, ecMedido);

        // Emite el JSON exactamente con el contrato de Atlachia
        imprimirObservacionJSON("conductividad", ecMedido, "mS/cm", calidad, 3);

        tiempoSimulado += INTERVALO_SEGUNDOS;
        std::this_thread::sleep_for(std::chrono::seconds(INTERVALO_SEGUNDOS));
    }

    return 0;
}