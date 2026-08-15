"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchBets, fetchBetSummary, createBet, updateBet, deleteBet,
  type Bet, type BetCreate, type BetSummary,
} from "@/lib/api";

/* ── Status badge component ──────────────────────────────────────────────── */

function ResultBadge({ result }: { result: Bet["result"] }) {
  const cls: Record<string, string> = {
    won: "stat-badge-win",
    lost: "stat-badge-loss",
    pending: "stat-badge-pending",
    push: "stat-badge-push",
    void: "stat-badge-push",
  };
  return (
    <span className={cls[result] || "stat-badge-pending"}>
      {result.toUpperCase()}
    </span>
  );
}

/* ── Summary Cards ───────────────────────────────────────────────────────── */

function SummaryCards({ summary }: { summary: BetSummary }) {
  const cards = [
    {
      label: "Total Bets",
      value: summary.total_bets,
      icon: "📊",
    },
    {
      label: "Total Staked",
      value: `$${summary.total_staked.toFixed(2)}`,
      icon: "💰",
    },
    {
      label: "Total Profit",
      value: `${summary.total_profit >= 0 ? "+" : ""}$${summary.total_profit.toFixed(2)}`,
      color: summary.total_profit >= 0 ? "text-nfl-win" : "text-nfl-loss",
      icon: summary.total_profit >= 0 ? "📈" : "📉",
    },
    {
      label: "ROI",
      value: `${summary.roi_percent >= 0 ? "+" : ""}${summary.roi_percent.toFixed(1)}%`,
      color: summary.roi_percent >= 0 ? "text-nfl-win" : "text-nfl-loss",
      icon: "🎯",
    },
    {
      label: "Win Rate",
      value: `${summary.win_rate.toFixed(1)}%`,
      color: summary.win_rate >= 50 ? "text-nfl-win" : "text-nfl-loss",
      icon: "🏆",
    },
    {
      label: "Record",
      value: `${summary.wins}W - ${summary.losses}L - ${summary.pushes}P`,
      icon: "📋",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
      {cards.map((card) => (
        <div key={card.label} className="glass-card p-4 text-center">
          <span className="text-2xl mb-2 block">{card.icon}</span>
          <p className={`text-xl font-display font-bold ${card.color || "text-white"}`}>
            {card.value}
          </p>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mt-1">
            {card.label}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ── Bet Form ────────────────────────────────────────────────────────────── */

function BetForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<BetCreate>({
    bet_type: "moneyline",
    pick: "",
    odds_decimal: 1.91,
    odds_american: -110,
    stake: 100,
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createBet(form);
      setForm({ bet_type: "moneyline", pick: "", odds_decimal: 1.91, odds_american: -110, stake: 100, notes: "" });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bet");
    } finally {
      setSubmitting(false);
    }
  };

  // Auto-compute decimal from american and vice versa
  const setAmerican = (val: number) => {
    const decimal = val > 0 ? 1 + val / 100 : 1 + 100 / Math.abs(val);
    setForm({ ...form, odds_american: val, odds_decimal: parseFloat(decimal.toFixed(3)) });
  };

  return (
    <form onSubmit={handleSubmit} className="glass-card p-6 mb-8">
      <h2 className="text-lg font-display font-semibold text-white mb-5">
        Log New Bet
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {/* Bet Type */}
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Type</label>
          <select
            value={form.bet_type}
            onChange={(e) => setForm({ ...form, bet_type: e.target.value })}
            className="input-field"
          >
            <option value="moneyline">Moneyline</option>
            <option value="spread">Spread</option>
            <option value="over_under">Over/Under</option>
            <option value="prop">Prop</option>
            <option value="parlay">Parlay</option>
          </select>
        </div>

        {/* Pick */}
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Pick</label>
          <input
            type="text"
            value={form.pick}
            onChange={(e) => setForm({ ...form, pick: e.target.value })}
            placeholder="e.g. KC Chiefs -3.5"
            className="input-field"
            required
          />
        </div>

        {/* American Odds */}
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">
            Odds (American)
          </label>
          <input
            type="number"
            value={form.odds_american ?? ""}
            onChange={(e) => setAmerican(parseInt(e.target.value) || -110)}
            className="input-field"
          />
        </div>

        {/* Stake */}
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Stake ($)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.stake}
            onChange={(e) => setForm({ ...form, stake: parseFloat(e.target.value) || 0 })}
            className="input-field"
            required
          />
        </div>
      </div>

      {/* Notes */}
      <div className="mb-4">
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Notes (optional)</label>
        <input
          type="text"
          value={form.notes || ""}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          placeholder="Reasoning, model output, edge identified..."
          className="input-field"
        />
      </div>

      {/* Calculated payout preview */}
      <div className="flex items-center justify-between mb-4 px-1">
        <p className="text-xs text-gray-500">
          Decimal odds: <span className="text-gray-300 font-mono">{form.odds_decimal.toFixed(3)}</span>
        </p>
        <p className="text-xs text-gray-500">
          Potential payout:{" "}
          <span className="text-nfl-win font-semibold">
            ${(form.stake * form.odds_decimal).toFixed(2)}
          </span>
        </p>
      </div>

      {error && (
        <p className="text-sm text-nfl-loss mb-3">{error}</p>
      )}

      <button type="submit" disabled={submitting || !form.pick} className="btn-primary w-full">
        {submitting ? "Saving..." : "Log Bet"}
      </button>
    </form>
  );
}

/* ── Bet History Table ───────────────────────────────────────────────────── */

function BetTable({
  bets,
  onResolve,
  onDelete,
}: {
  bets: Bet[];
  onResolve: (id: number, result: "won" | "lost" | "push") => void;
  onDelete: (id: number) => void;
}) {
  if (bets.length === 0) {
    return (
      <div className="glass-card p-10 text-center">
        <p className="text-gray-500 text-sm">No bets logged yet. Start tracking above!</p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="text-left px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Date
              </th>
              <th className="text-left px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Type
              </th>
              <th className="text-left px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Pick
              </th>
              <th className="text-right px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Odds
              </th>
              <th className="text-right px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Stake
              </th>
              <th className="text-right px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Profit
              </th>
              <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Result
              </th>
              <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {bets.map((bet) => (
              <tr key={bet.id} className="hover:bg-surface-700/30 transition-colors">
                <td className="px-5 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {bet.created_at
                    ? new Date(bet.created_at).toLocaleDateString("en-US", {
                      month: "short", day: "numeric",
                    })
                    : "—"}
                </td>
                <td className="px-5 py-3 text-gray-300 capitalize whitespace-nowrap">
                  {bet.bet_type.replace("_", "/")}
                </td>
                <td className="px-5 py-3 text-white font-medium max-w-[200px] truncate">
                  {bet.pick}
                </td>
                <td className="px-5 py-3 text-right text-gray-300 font-mono text-xs">
                  {bet.odds_american != null
                    ? (bet.odds_american > 0 ? `+${bet.odds_american}` : bet.odds_american)
                    : bet.odds_decimal.toFixed(2)}
                </td>
                <td className="px-5 py-3 text-right text-gray-300 font-mono">
                  ${bet.stake.toFixed(2)}
                </td>
                <td className={`px-5 py-3 text-right font-mono font-semibold
                  ${bet.profit > 0 ? "text-nfl-win" : bet.profit < 0 ? "text-nfl-loss" : "text-gray-400"}`}>
                  {bet.profit > 0 ? "+" : ""}{bet.profit.toFixed(2)}
                </td>
                <td className="px-5 py-3 text-center">
                  <ResultBadge result={bet.result} />
                </td>
                <td className="px-5 py-3 text-center">
                  {bet.result === "pending" ? (
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => onResolve(bet.id, "won")}
                        className="px-2 py-1 text-[10px] font-semibold rounded-lg
                                   bg-nfl-win/10 text-nfl-win hover:bg-nfl-win/20 transition-colors"
                        title="Mark as Won"
                      >
                        W
                      </button>
                      <button
                        onClick={() => onResolve(bet.id, "lost")}
                        className="px-2 py-1 text-[10px] font-semibold rounded-lg
                                   bg-nfl-loss/10 text-nfl-loss hover:bg-nfl-loss/20 transition-colors"
                        title="Mark as Lost"
                      >
                        L
                      </button>
                      <button
                        onClick={() => onResolve(bet.id, "push")}
                        className="px-2 py-1 text-[10px] font-semibold rounded-lg
                                   bg-nfl-push/10 text-nfl-push hover:bg-nfl-push/20 transition-colors"
                        title="Mark as Push"
                      >
                        P
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => onDelete(bet.id)}
                      className="text-gray-500 hover:text-nfl-loss transition-colors text-xs"
                      title="Delete"
                    >
                      ✕
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   BetTracker — Main Export
   ═══════════════════════════════════════════════════════════════════════════ */

export default function BetTracker() {
  const [bets, setBets] = useState<Bet[]>([]);
  const [summary, setSummary] = useState<BetSummary>({
    total_bets: 0, total_staked: 0, total_profit: 0,
    roi_percent: 0, wins: 0, losses: 0, pushes: 0, pending: 0, win_rate: 0,
  });
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [b, s] = await Promise.all([fetchBets(), fetchBetSummary()]);
      setBets(b);
      setSummary(s);
    } catch (err) {
      console.error("Failed to fetch bets:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleResolve = async (id: number, result: "won" | "lost" | "push") => {
    try {
      await updateBet(id, { result });
      await refresh();
    } catch (err) {
      console.error("Failed to resolve bet:", err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Delete this bet?")) return;
    try {
      await deleteBet(id);
      await refresh();
    } catch (err) {
      console.error("Failed to delete bet:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <SummaryCards summary={summary} />
      <BetForm onCreated={refresh} />

      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Bet History
      </h2>
      <BetTable bets={bets} onResolve={handleResolve} onDelete={handleDelete} />
    </div>
  );
}
