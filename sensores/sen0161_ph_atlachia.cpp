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
// 2. CONSTANTES DEL SENSOR DFRobot SEN0161-V2
// ==========================================
constexpr double NEUTRAL_VOLTAGE_DEF = 1500.0;  // mV a pH 7.0 (25 °C)
constexpr double ACID_VOLTAGE_DEF    = 2032.44; // mV a pH 4.0 (25 °C)

// ADC de 12 bits (como ESP32) a 3.3V
constexpr double ADC_VREF_MV   = 3300.0;
constexpr double ADC_MAX       = 4095.0;
constexpr double SENSOR_MAX_MV = 3000.0;        // Salida máxima útil de la placa V2

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
// 4. CLASE SIMULADORA DEL SENSOR SEN0161-V2
// ==========================================
class SensorPHVirtual {
private:
    double neutralVoltage;
    double acidVoltage;
    double slope;
    double intercept;

    std::mt19937 gen;
    std::normal_distribution<double> ruidoVoltaje;

    void actualizarCurva() {
        slope = (7.0 - 4.0) / (((neutralVoltage - 1500.0) / 3.0) - ((acidVoltage - 1500.0) / 3.0));
        intercept = 7.0 - slope * ((neutralVoltage - 1500.0) / 3.0);
    }

public:
    SensorPHVirtual(double desviacionRuidoMv = 3.5)
        : neutralVoltage(NEUTRAL_VOLTAGE_DEF),
          acidVoltage(ACID_VOLTAGE_DEF),
          gen(std::random_device{}()),
          ruidoVoltaje(0.0, desviacionRuidoMv) {
        actualizarCurva();
    }

    int simularLecturaADC(double phReal) {
        phReal = std::clamp(phReal, 0.0, 14.0);
        double voltajeIdeal_mV = 1500.0 + 3.0 * ((phReal - intercept) / slope);

        double voltajeConRuido_mV = std::clamp(voltajeIdeal_mV + ruidoVoltaje(gen), 0.0, SENSOR_MAX_MV);
        int valorADC = static_cast<int>(std::round((voltajeConRuido_mV / ADC_VREF_MV) * ADC_MAX));
        return std::clamp(valorADC, 0, static_cast<int>(ADC_MAX));
    }

    double leerPH(int valorADC) const {
        double voltaje_mV = (valorADC / ADC_MAX) * ADC_VREF_MV;
        double phValue = slope * ((voltaje_mV - 1500.0) / 3.0) + intercept;
        return std::clamp(phValue, 0.0, 14.0);
    }

    // Evalúa la calidad según los límites eléctricos del ADC y la escala física de pH
    std::string evaluarCalidad(int valorADC, double phMedido) const {
        if (valorADC <= 0 || valorADC >= static_cast<int>(ADC_MAX)) {
            return "descartado"; // Posible desconexión de sonda BNC o corto
        }
        if (phMedido < 0.0 || phMedido > 14.0) {
            return "descartado";
        }
        return "validado";
    }

    void calibrar(double voltajeNeutral_mV, double voltajeAcido_mV) {
        neutralVoltage = voltajeNeutral_mV;
        acidVoltage = voltajeAcido_mV;
        actualizarCurva();
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
    SensorPHVirtual sensor(3.5);
    const int INTERVALO_SEGUNDOS = intervaloSegundos();
    double tiempoSimulado = 0.0;

    while (true) {
        // Simula pH típico de agua superficial/presa (entre 6.8 y 8.2 pH)
        double phReal = 7.5 + 0.7 * std::sin(tiempoSimulado * 0.1);
        if (descargaActiva()) phReal -= 0.6;          // descarga: agua más ácida

        int adc = sensor.simularLecturaADC(phReal);
        double phMedido = sensor.leerPH(adc);
        std::string calidad = sensor.evaluarCalidad(adc, phMedido);

        // Emite el JSON exactamente con el contrato de Atlachia
        imprimirObservacionJSON("pH", phMedido, "pH", calidad, 2);

        tiempoSimulado += INTERVALO_SEGUNDOS;
        std::this_thread::sleep_for(std::chrono::seconds(INTERVALO_SEGUNDOS));
    }

    return 0;
}