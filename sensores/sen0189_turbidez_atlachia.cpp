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
// 2. CONSTANTES DEL SENSOR DFRobot SEN0189
// ==========================================
constexpr double ADC_VREF_V    = 5.0;
constexpr double ADC_MAX       = 1024.0;
constexpr double V_AGUA_LIMPIA = 4.2;
constexpr double V_TURBIDEZ_MAX = 2.5;
constexpr double NTU_MAX       = 3000.0;

constexpr double COEF_A = -1120.4;
constexpr double COEF_B = 5742.3;
constexpr double COEF_C = -4352.9;

// ==========================================
// 3. FUNCIONES MOLDE (REUTILIZABLES PARA TODOS LOS SENSORES)
// ==========================================

// Genera la fecha actual en formato ISO 8601 UTC: "YYYY-MM-DDTHH:MM:SS.mmmZ"
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

// Emite una observación en el formato común exacto de Atlachia
void imprimirObservacionJSON(const std::string& parametro,
                             double valor,
                             const std::string& unidad,
                             const std::string& calidad,
                             int decimales = 1) {
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
// 4. CLASE SIMULADORA DEL SENSOR SEN0189
// ==========================================
class SensorTurbidezVirtual {
private:
    std::mt19937 gen;
    std::normal_distribution<double> ruidoVoltaje;

public:
    SensorTurbidezVirtual(double desviacionRuidoV = 0.015)
        : gen(std::random_device{}()),
          ruidoVoltaje(0.0, desviacionRuidoV) {}

    int simularLecturaADC(double ntuReal) {
        ntuReal = std::clamp(ntuReal, 0.0, NTU_MAX);

        double discriminante = (COEF_B * COEF_B) - 4.0 * (-COEF_A) * (-COEF_C + ntuReal);
        double voltajeIdeal_V = V_TURBIDEZ_MAX;

        if (discriminante >= 0.0) {
            voltajeIdeal_V = (COEF_B + std::sqrt(discriminante)) / (2.0 * (-COEF_A));
        }

        double voltajeConRuido_V = std::clamp(voltajeIdeal_V + ruidoVoltaje(gen), 0.0, 4.5);
        int valorADC = static_cast<int>(std::round((voltajeConRuido_V / ADC_VREF_V) * ADC_MAX));
        return std::clamp(valorADC, 0, 1023);
    }

    double leerNTU(double valorADC) const {
        double voltaje_V = valorADC * (ADC_VREF_V / ADC_MAX);
        if (voltaje_V <= V_TURBIDEZ_MAX) return NTU_MAX;
        if (voltaje_V >= V_AGUA_LIMPIA)  return 0.0;

        double ntu = (COEF_A * voltaje_V * voltaje_V) + (COEF_B * voltaje_V) + COEF_C;
        return std::clamp(ntu, 0.0, NTU_MAX);
    }

    // Evalúa la calidad de la lectura según el voltaje físico del sensor
    std::string evaluarCalidad(int valorADC) const {
        double voltaje_V = valorADC * (ADC_VREF_V / ADC_MAX);
        // Si el voltaje cae por debajo de 0.5V (posible cable desconectado o corto), se descarta
        if (voltaje_V < 0.5 || voltaje_V > 4.6) {
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
    SensorTurbidezVirtual sensor(0.015);
    const int INTERVALO_SEGUNDOS = intervaloSegundos();
    double tiempoSimulado = 0.0;

    while (true) {
        // Simula una variación realista de turbidez en la presa (entre 10 y 60 NTU)
        double ntuReal = 35.0 + 25.0 * std::sin(tiempoSimulado * 0.15);
        if (descargaActiva()) ntuReal += 150.0;       // descarga: sólidos suspendidos

        // Promedia 40 lecturas del ADC (como el ejemplo oficial de DFRobot) para reducir el ruido
        constexpr int MUESTRAS = 40;
        double sumaADC = 0.0;
        for (int k = 0; k < MUESTRAS; ++k) sumaADC += sensor.simularLecturaADC(ntuReal);
        double adcPromedio = sumaADC / MUESTRAS;
        double ntuMedido = sensor.leerNTU(adcPromedio);
        std::string calidad = sensor.evaluarCalidad(static_cast<int>(std::lround(adcPromedio)));

        // Emite el JSON exactamente con el contrato de Atlachia
        imprimirObservacionJSON("turbidez", ntuMedido, "NTU", calidad, 1);

        tiempoSimulado += INTERVALO_SEGUNDOS;
        std::this_thread::sleep_for(std::chrono::seconds(INTERVALO_SEGUNDOS));
    }

    return 0;
}