import LiveGamesBoard from "@/components/LiveGamesBoard";

export const metadata = {
  title: "Live Games — NFL BetMaster",
  description: "Real-time NFL scoreboard with live scores, odds, and field position.",
};

export default function LivePage() {
  return (
    <div>
      {/* ── Page Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">
          Live Scoreboard
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Real-time scores, odds, and field position updates via SSE
        </p>
      </div>

      {/* ── Live Board ── */}
      <LiveGamesBoard />
    </div>
  );
}
