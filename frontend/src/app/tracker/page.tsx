import BetTracker from "@/components/BetTracker";

export const metadata = {
  title: "Bet Tracker — NFL BetMaster",
  description: "Track your NFL bets, monitor ROI, and analyze your betting performance.",
};

export default function TrackerPage() {
  return (
    <div>
      {/* ── Page Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">
          Bet Tracker
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Log bets, track your ROI, and review performance over time
        </p>
      </div>

      {/* ── Tracker ── */}
      <BetTracker />
    </div>
  );
}
