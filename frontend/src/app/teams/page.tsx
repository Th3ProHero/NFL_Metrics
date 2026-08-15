"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { fetchTeams, type Team } from "@/lib/api";

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTeams()
      .then(setTeams)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
      </div>
    );
  }

  // Group by conference
  const afc = teams.filter(t => t.conference === "AFC");
  const nfc = teams.filter(t => t.conference === "NFC");

  const renderConference = (confTeams: Team[], confName: string) => (
    <section className="mb-10">
      <h2 className="text-xl font-display font-bold text-white mb-6 uppercase tracking-wider flex items-center gap-2">
        <span className={`w-3 h-3 rounded-full ${confName === "AFC" ? "bg-red-500" : "bg-blue-500"}`} />
        {confName}
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
        {confTeams.map((team) => (
          <Link key={team.id} href={`/teams/${team.id}`} className="group relative block">
            <div className="glass-card p-4 aspect-square flex flex-col items-center justify-center transition-all duration-300 hover:bg-surface-700/50 hover:scale-105 border border-transparent hover:border-white/10 overflow-hidden">
              {team.logo_url ? (
                <div className="relative w-16 h-16 transition-transform group-hover:scale-110">
                  <Image src={team.logo_url} alt={team.name} fill className="object-contain" unoptimized />
                </div>
              ) : (
                <div className="w-16 h-16 bg-surface-800 rounded-full flex items-center justify-center font-bold text-gray-500">
                  {team.abbreviation}
                </div>
              )}
              <div className="mt-3 text-center">
                <p className="text-sm font-bold text-gray-300 group-hover:text-white transition-colors">{team.abbreviation}</p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wide truncate w-full px-1">{team.name}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );

  return (
    <div className="max-w-7xl mx-auto">
      <header className="mb-10">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">NFL Teams Hub</h1>
        <p className="text-gray-400 mt-2">Select a team to view their detailed performance analytics, recent history, and upcoming mathematical projections.</p>
      </header>
      
      {renderConference(afc, "AFC")}
      {renderConference(nfc, "NFC")}
    </div>
  );
}