# NFL BetMaster 🏈

Plataforma de análisis deportivo, rastreo de cuotas y gestión de apuestas para la NFL (100% gratuita y auto-hospedada).

## 📖 Guía de Uso para Principiantes

Si eres nuevo en el mundo de las apuestas deportivas, aquí tienes todo lo que necesitas saber para sacarle el máximo provecho a la aplicación.

### 1. Diccionario Básico de Apuestas

*   **Moneyline (A ganar):** Es la apuesta más simple. Solo eliges quién va a ganar el partido, sin importar la diferencia de puntos.
*   **Spread (Hándicap):** Para igualar las cosas, el casino le resta puntos al favorito y le suma puntos al menos favorito (Underdog). 
    *   *Ejemplo:* Si ves "Chiefs -3.5", significa que los Chiefs deben ganar por 4 puntos o más para que tu apuesta gane. Si ves "Raiders +3.5", los Raiders pueden ganar el partido o perder hasta por 3 puntos y tu apuesta aún será ganadora.
*   **Over / Under (Altas / Bajas):** Apuestas a la suma total de puntos anotados por ambos equipos. Si la línea es 45.5, el *Over (Altas)* gana si anotan 46 o más, y el *Under (Bajas)* gana si anotan 45 o menos.
*   **Cuotas (Odds):** Representan tu pago potencial. Usamos el formato "Americano".
    *   **Negativas (Ej. -110):** Indican cuánto tienes que apostar para ganar $100. (Apostar $110 te da $100 de ganancia). Suelen ser los favoritos.
    *   **Positivas (Ej. +150):** Indican cuánto ganarás si apuestas $100. (Apostar $100 te da $150 de ganancia). Suelen ser los *underdogs*.
*   **+EV (Expected Value / Valor Esperado Positivo):** Es el "Santo Grial" matemático. Significa que, a largo plazo, una apuesta es rentable porque el casino te está pagando mejor de lo que la probabilidad real del evento sugiere. **Nuestra aplicación está diseñada para buscar estas apuestas.**

---

### 2. ¿Cómo usar las herramientas de la App?

#### 🔴 Live Scoreboard (Marcador en Vivo)
*   **¿Qué es?** Es tu pantalla principal durante los días de partido. Se actualiza en tiempo real sin recargar la página.
*   **El Truco Oculto:** ¡Haz clic en cualquier tarjeta de un partido! La tarjeta se expandirá y nuestra computadora simulará el partido 10,000 veces al instante.
*   **¿Cómo leerlo?** Te mostrará el `%` real de victoria de cada equipo. Abajo verás un recuadro. Si aparece una **"🔥 ACCIÓN RECOMENDADA"**, hazle caso: el modelo encontró una apuesta rentable. Si dice **"✋ PASAR"**, no apuestes, el riesgo no vale la pena.

#### 📈 Analysis (Buscador de Ventajas)
*   **¿Qué es?** Es para estudiar los partidos *antes* de que empiecen.
*   **¿Cómo usarlo?** Revisa la columna de "Signal". La app compara lo que dicen los casinos contra nuestros algoritmos matemáticos (basados en eficiencia EPA). Si detecta un desajuste grosero, te lo marcará como una oportunidad.
*   **Deep Dive:** Abajo puedes seleccionar a tu equipo favorito para ver su eficiencia ofensiva y defensiva real (EPA / Play).

#### 💰 Bet Tracker (Gestor de Apuestas)
*   **¿Qué es?** Aquí es donde anotas todas tus apuestas reales (o ficticias si estás practicando). Es vital para saber si eres rentable.
*   **¿Cómo usarlo?** 
    1.  Ve a "Log New Bet".
    2.  Selecciona qué apostaste, escribe tu pick (ej. "Eagles Spread -2.5"), pon la cuota americana (el sistema calculará el pago solo) y tu inversión.
    3.  Cuando el partido acabe, dale clic en la "W" (Ganada) o "L" (Perdida) en tu historial. El sistema sumará el dinero a tu banco y calculará tu **ROI%** (Retorno de Inversión). ¡El objetivo es mantener el ROI en verde!

---

## 🛠 Instalación Rápida (Servidor Local)

```bash
# 1. Clonar el repositorio
git clone https://github.com/Th3ProHero/NFL_Metrics.git
cd NFL_Metrics

# 2. Configurar IP (Crucial para ver el sitio en otros dispositivos)
# IMPORTANTE: Cambia '192.168.0.220' por la IP real de tu máquina/servidor
cat <<EOT > .env
NEXT_PUBLIC_API_URL=http://192.168.0.220:8000
CORS_ORIGINS=http://192.168.0.220:4000,http://localhost:4000
EOT

# 3. Construir e iniciar contenedores
docker-compose up --build -d

# 4. Acceder al dashboard
# Abre en el navegador de tu computadora o celular: http://[TU_IP]:4000
```

## 🏗 Arquitectura

| Servicio   | Puerto | Descripción                           |
|------------|--------|---------------------------------------|
| Frontend   | 4000   | Next.js App Router (React + Tailwind) |
| Backend    | 8000   | FastAPI REST (Numba CPU Monte Carlo)  |
| PostgreSQL | 5440   | Base de datos estructurada            |

## 📊 Fuentes de Datos

*   [ESPN Scoreboard API](https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard) (En vivo, gratuito)
*   [The Odds API](https://the-odds-api.com) (Historial y líneas base de casinos)
*   `nfl_data_py` (Datos históricos y eficiencia EPA)
