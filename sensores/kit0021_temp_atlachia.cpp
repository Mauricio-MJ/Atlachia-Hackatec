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
#include <cstdint>

// ==========================================
// 1. CONFIGURACIÓN DEL NODO (ATLACHIA)
// ==========================================
constexpr const char* FUENTE = "iot";
constexpr const char* SITIO  = "NODO-01";     // Entrada del río Atoyac en Valsequillo
constexpr double LATITUD     = 18.948;
constexpr double LONGITUD    = -98.250;

// ==========================================
// 2. CONSTANTES DEL SENSOR DS18B20 (KIT0021)
// ==========================================
constexpr double TEMP_MIN_C       = -55.0;
constexpr double TEMP_MAX_C       = 125.0;
constexpr double RESOLUCION_12BIT = 0.0625;   // Paso mínimo a 12 bits (1/16 °C)
constexpr int16_t RAW_DESCONECTADO = -2032;   // Equivale a -127.0 °C (error 1-Wire)

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
// 4. CLASE SIMULADORA DEL SENSOR DS18B20
// ==========================================
class SensorDS18B20Virtual {
private:
    std::mt19937 gen;
    std::normal_distribution<double> ruidoTermico;

public:
    SensorDS18B20Virtual(double desviacionRuidoC = 0.15)
        : gen(std::random_device{}()),
          ruidoTermico(0.0, desviacionRuidoC) {}

    int16_t simularRegistroRaw(double tempReal_C, bool sensorConectado = true) {
        if (!sensorConectado) {
            return RAW_DESCONECTADO;
        }

        double tempConRuido = std::clamp(tempReal_C + ruidoTermico(gen), TEMP_MIN_C, TEMP_MAX_C);
        return static_cast<int16_t>(std::round(tempConRuido / RESOLUCION_12BIT));
    }

    double leerTemperaturaC(int16_t registroRaw) const {
        if (registroRaw == RAW_DESCONECTADO) {
            return -127.0;
        }
        return static_cast<double>(registroRaw) * RESOLUCION_12BIT;
    }

    // Evalúa la calidad según el registro digital 1-Wire y rangos físicos del agua
    std::string evaluarCalidad(int16_t registroRaw) const {
        if (registroRaw == RAW_DESCONECTADO) {
            return "descartado";
        }
        double temp = leerTemperaturaC(registroRaw);
        // En una presa como Valsequillo, lecturas fuera de 0 °C a 50 °C indican fallo de sonda
        if (temp < 0.0 || temp > 50.0) {
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
    SensorDS18B20Virtual sensor(0.15);
    const int INTERVALO_SEGUNDOS = intervaloSegundos();
    double tiempoSimulado = 0.0;

    while (true) {
        // Simula temperatura superficial típica de la presa Valsequillo (18 °C a 22 °C)
        double tempReal = 20.0 + 2.0 * std::sin(tiempoSimulado * 0.05);
        if (descargaActiva()) tempReal += 0.8;        // descarga: agua residual más tibia

        int16_t raw = sensor.simularRegistroRaw(tempReal, true);
        double tempMedida = sensor.leerTemperaturaC(raw);
        std::string calidad = sensor.evaluarCalidad(raw);

        // Emite el JSON exactamente con el contrato de Atlachia
        imprimirObservacionJSON("temperatura", tempMedida, "°C", calidad, 2);

        tiempoSimulado += INTERVALO_SEGUNDOS;
        std::this_thread::sleep_for(std::chrono::seconds(INTERVALO_SEGUNDOS));
    }

    return 0;
}