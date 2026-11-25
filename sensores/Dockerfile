# Atlachia · contenedor de sensores: compila los 5 simuladores C++ y corre el puente en Python
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.cpp ./
RUN mkdir -p bin && for f in *.cpp; do g++ -std=c++17 -O2 -o "bin/${f%_atlachia.cpp}" "$f"; done
COPY puente.py .
CMD ["python", "-u", "puente.py"]
