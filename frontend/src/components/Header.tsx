"use client";

import React, { useState, useEffect } from "react";
import {
  Menu,
  X,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Network,
  CheckSquare,
} from "lucide-react";
import { StatsResponse } from "@/types";

interface HeaderProps {
  stats: StatsResponse | null;
  loadingStats: boolean;
}

export const Header: React.FC<HeaderProps> = ({ stats, loadingStats }) => {
  const [isOpen, setIsOpen] = useState(false);

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <>
      {/* ======================================================== */}
      {/* TOP NAVIGATION BAR                                       */}
      {/* ======================================================== */}
      <header className="border-b border-slate-800 bg-[#0F172A]/90 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 lg:px-10 py-3.5">
        <div className="w-full flex items-center justify-between gap-4">
          {/* Left: 3-line Hamburger Menu Button + Brand Logo & Title */}
          <div className="flex items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-2 shadow-xs group"
              aria-label="Open sidebar menu"
              title="Open Stats & Verification Checklist"
            >
              <Menu className="w-5 h-5 text-slate-300 group-hover:text-white transition-colors" />
              <span className="text-xs font-semibold text-slate-300 group-hover:text-white transition-colors hidden sm:inline">
                Menu
              </span>
            </button>

            <div className="flex items-center gap-3">
              <img
                src="/logo.jpg"
                alt="ScamShield Logo"
                className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl object-cover border border-slate-700/80 shadow-sm shrink-0"
              />
              <div>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white leading-tight flex items-center gap-1.5">
                  ScamShield
                  <span className="bg-gradient-to-r from-indigo-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent font-extrabold">
                    AI
                  </span>
                </h1>
                <p className="text-xs sm:text-sm text-slate-400 font-normal">
                  Career Verification Portal
                </p>
              </div>
            </div>
          </div>

          {/* Right: Compact Live Stat Pills */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Checked */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Checked:</span>
              <span className="font-bold text-white">
                {loadingStats ? "..." : (stats?.total_investigations ?? 0)}
              </span>
            </div>

            {/* Safe */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className="text-[10px] uppercase font-semibold text-emerald-400">Safe:</span>
              <span className="font-bold text-emerald-400">
                {loadingStats ? "..." : (stats?.safe_count ?? 0)}
              </span>
            </div>

            {/* Scams Flagged */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className="text-[10px] uppercase font-semibold text-red-400">Flagged:</span>
              <span className="font-bold text-red-400">
                {loadingStats ? "..." : (stats?.high_risk_count ?? 0)}
              </span>
            </div>

            {/* Linked Scams */}
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className="text-[10px] uppercase font-semibold text-amber-400">Linked:</span>
              <span className="font-bold text-amber-400">
                {loadingStats ? "..." : (stats?.coordinated_campaigns_count ?? 0)}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ======================================================== */}
      {/* SLIDE-OUT DRAWER BACKDROP OVERLAY                        */}
      {/* ======================================================== */}
      <div
        className={`fixed inset-0 bg-black/60 backdrop-blur-xs z-50 transition-opacity duration-300 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setIsOpen(false)}
        aria-hidden="true"
      />

      {/* ======================================================== */}
      {/* SLIDE-OUT DRAWER SIDEBAR                                 */}
      {/* ======================================================== */}
      <aside
        className={`fixed inset-y-0 left-0 w-80 max-w-[85vw] bg-[#0F172A] border-r border-slate-800 p-6 z-50 shadow-2xl flex flex-col justify-between overflow-y-auto transform transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Sidebar navigation"
      >
        <div className="space-y-6">
          {/* Drawer Header with Close Button (X) */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src="/logo.jpg"
                alt="ScamShield Logo"
                className="w-11 h-11 rounded-xl object-cover border border-slate-700/80 shadow-sm shrink-0"
              />
              <div>
                <h2 className="text-xl font-bold tracking-tight text-white leading-tight flex items-center gap-1.5">
                  ScamShield
                  <span className="bg-gradient-to-r from-indigo-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent font-extrabold">
                    AI
                  </span>
                </h2>
                <p className="text-xs text-slate-400 font-normal">
                  Career Verification Portal
                </p>
              </div>
            </div>

            {/* Close Button (X) */}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 transition-colors"
              aria-label="Close sidebar menu"
              title="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="h-px bg-slate-800/80" />

          {/* Platform Stats: Vertical Stack */}
          <div className="space-y-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Live Investigation Stats
            </p>

            <div className="space-y-2">
              {/* 1) Checked */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-300">
                <div className="flex items-center gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-medium text-slate-300">Checked</span>
                </div>
                <span className="text-sm font-bold text-white">
                  {loadingStats ? "..." : (stats?.total_investigations ?? 0)}
                </span>
              </div>

              {/* 2) Safe */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-300">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-medium text-slate-300">Safe</span>
                </div>
                <span className="text-sm font-bold text-emerald-400">
                  {loadingStats ? "..." : (stats?.safe_count ?? 0)}
                </span>
              </div>

              {/* 3) Scams Flagged */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-300">
                <div className="flex items-center gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-medium text-slate-300">Scams Flagged</span>
                </div>
                <span className="text-sm font-bold text-red-400">
                  {loadingStats ? "..." : (stats?.high_risk_count ?? 0)}
                </span>
              </div>

              {/* 4) Linked Scams */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-300">
                <div className="flex items-center gap-2.5">
                  <Network className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-medium text-slate-300">Linked Scams</span>
                </div>
                <span className="text-sm font-bold text-amber-400">
                  {loadingStats ? "..." : (stats?.coordinated_campaigns_count ?? 0)}
                </span>
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-800/80" />

          {/* 4-Point Check Info Box */}
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 text-slate-300 space-y-2.5">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                4-Point Check
              </h3>
            </div>
            <ul className="text-xs text-slate-400 space-y-1.5 font-medium pl-1">
              <li className="flex items-center gap-2">
                <span className="text-indigo-400 text-[11px] font-bold">1.</span>
                <span>Fee & UPI Traps</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-indigo-400 text-[11px] font-bold">2.</span>
                <span>Aadhaar / PAN Requests</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-indigo-400 text-[11px] font-bold">3.</span>
                <span>Fake Domains</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-indigo-400 text-[11px] font-bold">4.</span>
                <span>Repeat Scam Links</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="pt-6 border-t border-slate-800/80 text-[11px] text-slate-500">
          <p className="font-semibold text-slate-400">Student Defense Portal</p>
          <p className="mt-0.5">Protecting candidates against recruitment fraud.</p>
        </div>
      </aside>
    </>
  );
};
