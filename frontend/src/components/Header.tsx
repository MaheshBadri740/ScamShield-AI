"use client";

import React from "react";
import { ShieldCheck, CheckCircle2, AlertTriangle, Network } from "lucide-react";
import { StatsResponse } from "@/types";

interface HeaderProps {
  stats: StatsResponse | null;
  loadingStats: boolean;
}

export const Header: React.FC<HeaderProps> = ({ stats, loadingStats }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Logo & Tagline */}
          <div className="flex items-center gap-3">
            <img
              src="/logo.jpg"
              alt="ScamShield AI Logo"
              className="w-11 h-11 rounded-xl object-cover shadow-md border border-cyan-500/30"
            />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-white">
                  ScamShield <span className="text-cyan-400">AI</span>
                </h1>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-800 text-cyan-300">
                  Student Defense
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 font-medium">
                Verify Every Opportunity. Protect Your Future.
              </p>
            </div>
          </div>

          {/* Live Stats Bar: 4 Clean Badges */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
            {/* 1) Checked */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-cyan-900/40 text-slate-300">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              <div className="text-xs">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Checked</span>
                <span className="font-bold text-white">
                  {loadingStats ? "..." : (stats?.total_investigations ?? 0)}
                </span>
              </div>
            </div>

            {/* 2) Safe */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-emerald-950/60 text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <div className="text-xs">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Safe</span>
                <span className="font-bold text-emerald-400">
                  {loadingStats ? "..." : (stats?.safe_count ?? 0)}
                </span>
              </div>
            </div>

            {/* 3) Scams Flagged */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-red-950/60 text-slate-300">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <div className="text-xs">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Scams Flagged</span>
                <span className="font-bold text-red-400">
                  {loadingStats ? "..." : (stats?.high_risk_count ?? 0)}
                </span>
              </div>
            </div>

            {/* 4) Linked Scams */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-amber-950/60 text-slate-300">
              <Network className="w-4 h-4 text-amber-400" />
              <div className="text-xs">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Linked Scams</span>
                <span className="font-bold text-amber-400">
                  {loadingStats ? "..." : (stats?.coordinated_campaigns_count ?? 0)}
                </span>
              </div>
            </div>

            <div className="hidden xl:flex items-center gap-1.5 pl-2 text-[11px] text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Defense
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
