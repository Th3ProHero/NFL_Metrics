import React from "react";

export const metadata = {
  title: "Betting Guide | NFL BetMaster",
};

export default function GuidePage() {
  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">
          Betting 101: Guía para Principiantes
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Aprende los conceptos básicos y descubre cómo usar la inteligencia de esta plataforma para encontrar ventaja.
        </p>
      </div>

      <div className="space-y-10">
        {/* Section 1: Dictionary */}
        <section>
          <h2 className="text-lg font-display font-semibold text-accent-blue mb-4 flex items-center gap-2">
            <span className="text-2xl">📚</span> Diccionario Básico de Apuestas
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="glass-card p-5">
              <h3 className="text-white font-bold mb-2">Moneyline (A ganar)</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                Es la apuesta más simple de todas. Solo eliges quién va a ganar el partido, sin importar por cuántos puntos de diferencia lo haga.
              </p>
            </div>
            <div className="glass-card p-5">
              <h3 className="text-white font-bold mb-2">Spread (Hándicap)</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                Para igualar las cosas, el casino le resta puntos al favorito y le suma puntos al <i>Underdog</i>. Si apuestas a <strong>Chiefs -3.5</strong>, deben ganar por 4 puntos o más. Si apuestas a <strong>Raiders +3.5</strong>, pueden perder hasta por 3 puntos y ganas.
              </p>
            </div>
            <div className="glass-card p-5">
              <h3 className="text-white font-bold mb-2">Over / Under (Altas / Bajas)</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                Apuestas a la suma total de puntos anotados por ambos equipos. Si la línea es <strong>45.5</strong>, el <i>Over</i> gana si anotan 46 o más, y el <i>Under</i> gana si anotan 45 o menos.
              </p>
            </div>
            <div className="glass-card p-5 border border-nfl-win/20 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-nfl-win"></div>
              <h3 className="text-nfl-win font-bold mb-2">+EV (Valor Esperado Positivo)</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                Es el "Santo Grial" matemático. Significa que, a largo plazo, una apuesta es rentable porque el casino te está pagando mejor de lo que la probabilidad real del evento sugiere. <strong>Nuestra aplicación está diseñada para buscar estas oportunidades.</strong>
              </p>
            </div>
          </div>
        </section>

        {/* Section 2: How to read odds */}
        <section>
          <h2 className="text-lg font-display font-semibold text-accent-purple mb-4 flex items-center gap-2">
            <span className="text-2xl">🔢</span> Cómo leer las Cuotas (Odds Americanas)
          </h2>
          <div className="glass-card p-6">
            <p className="text-sm text-gray-300 mb-4 leading-relaxed">
              Las cuotas indican tu pago potencial y la probabilidad que el casino le asigna a un evento. Utilizamos el formato "Americano".
            </p>
            <ul className="space-y-4 text-sm text-gray-400">
              <li className="flex items-start gap-3">
                <span className="bg-surface-800 text-white font-mono px-2 py-1 rounded border border-white/10 shrink-0">-110</span>
                <span>
                  <strong>Cuotas Negativas (Favoritos):</strong> Indican cuánto dinero tienes que apostar para ganar $100 de ganancia limpia. Es decir, debes apostar $110 para llevarte $100.
                </span>
              </li>
              <li className="flex items-start gap-3">
                <span className="bg-surface-800 text-white font-mono px-2 py-1 rounded border border-white/10 shrink-0">+150</span>
                <span>
                  <strong>Cuotas Positivas (Underdogs):</strong> Indican cuánto ganarás si apuestas exactamente $100. Es decir, apostar $100 te da $150 de ganancia limpia.
                </span>
              </li>
            </ul>
          </div>
        </section>

        {/* Section 3: App Features */}
        <section>
          <h2 className="text-lg font-display font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">⚡</span> ¿Cómo usar esta aplicación?
          </h2>
          <div className="space-y-4">
            <div className="glass-card p-6 flex flex-col md:flex-row gap-6 items-start">
              <div className="w-12 h-12 rounded-full bg-accent-blue/10 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-white font-bold mb-2">Live Scoreboard (El Marcador Inteligente)</h3>
                <p className="text-sm text-gray-400 leading-relaxed mb-3">
                  Es tu pantalla principal. <strong>El secreto:</strong> Haz clic en cualquier tarjeta de un partido.
                  Nuestra computadora simulará el partido 10,000 veces al instante.
                </p>
                <div className="bg-surface-800 p-3 rounded-lg border border-white/5 text-sm">
                  <p className="text-gray-300"><span className="text-nfl-win font-bold">🔥 ACCIÓN RECOMENDADA:</span> Si ves este mensaje verde, el modelo matemático ha encontrado una apuesta con un valor esperado muy alto. Deberías considerarla fuertemente.</p>
                  <p className="text-gray-300 mt-2"><span className="text-gray-500 font-bold">✋ PASAR:</span> Si ves este mensaje, el casino no está ofreciendo valor. Quédate quieto.</p>
                </div>
              </div>
            </div>

            <div className="glass-card p-6 flex flex-col md:flex-row gap-6 items-start">
              <div className="w-12 h-12 rounded-full bg-accent-purple/10 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 13h2l3-8 4 16 3-8h2M21 13h-2" />
                </svg>
              </div>
              <div>
                <h3 className="text-white font-bold mb-2">Analysis (Encontrar Ventajas Pre-partido)</h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  Úsalo para estudiar la jornada de NFL *antes* de que empiece. Revisa la tabla de juegos; la app compara lo que dicen los casinos contra nuestros algoritmos de eficiencia (EPA). Abajo puedes seleccionar a tu equipo para ver su eficiencia ofensiva y defensiva de forma profunda.
                </p>
              </div>
            </div>

            <div className="glass-card p-6 flex flex-col md:flex-row gap-6 items-start">
              <div className="w-12 h-12 rounded-full bg-nfl-win/10 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-nfl-win" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m-6 4h6m-6 4h4M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z" />
                </svg>
              </div>
              <div>
                <h3 className="text-white font-bold mb-2">Bet Tracker (Tu Contabilidad)</h3>
                <p className="text-sm text-gray-400 leading-relaxed mb-3">
                  Anota todas tus apuestas (reales o simuladas) para medir si tu estrategia es rentable a largo plazo.
                </p>
                <ul className="list-disc list-inside text-sm text-gray-400 space-y-1">
                  <li>Registra el partido, la cuota, y tu dinero arriesgado (Stake).</li>
                  <li>Al acabar, marca <strong>W</strong> (Ganada), <strong>L</strong> (Perdida) o <strong>P</strong> (Empate).</li>
                  <li>El sistema actualizará tu <strong>ROI% (Retorno de Inversión)</strong>. Manténlo en verde.</li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
