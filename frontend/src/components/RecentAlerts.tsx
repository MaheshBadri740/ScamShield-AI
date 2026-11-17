"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  Building,
  Calendar,
  RotateCw,
  EyeOff,
  Trash2,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { OpportunityReportItem, RiskLevel } from "@/types";
import { deleteReport, clearAllReports } from "@/lib/api";

interface RecentAlertsProps {
  reports: OpportunityReportItem[];
  isLoading: boolean;
  onRefresh: () => void;
  onReportsChanged?: () => void;
}

export const RecentAlerts: React.FC<RecentAlertsProps> = ({
  reports,
  isLoading,
  onRefresh,
  onReportsChanged,
}) => {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isClearing, setIsClearing] = useState<boolean>(false);

  const badgeColors: Record<RiskLevel, { bg: string; text: string; border: string }> = {
    HIGH: { bg: "bg-red-950/70", text: "text-red-400", border: "border-red-700/60" },
    MEDIUM: { bg: "bg-amber-950/70", text: "text-amber-400", border: "border-amber-700/60" },
    LOW: { bg: "bg-emerald-950/70", text: "text-emerald-400", border: "border-emerald-700/60" },
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Recent";
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "Recent";
    }
  };

  const handleDelete = async (reportId: number) => {
    setDeletingId(reportId);
    try {
      const success = await deleteReport(reportId);
      if (success) {
        onReportsChanged?.();
      }
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    if (reports.length === 0) return;
    const confirmed = window.confirm(
      "Are you sure you want to clear all recorded alerts and reset connected scam entities?"
    );
    if (!confirmed) return;

    setIsClearing(true);
    try {
      const success = await clearAllReports();
      if (success) {
        onReportsChanged?.();
      }
    } finally {
      setIsClearing(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-400" />
            Recent Community Scam Alerts
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 flex items-center gap-1.5">
            <EyeOff className="w-3.5 h-3.5 text-slate-500" />
            Anonymized intelligence from recent student opportunity checks.
          </p>
        </div>

        {/* Action Controls: Clear All & Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {reports.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              disabled={isClearing || isLoading}
              className="px-3 py-1.5 rounded-xl bg-red-950/40 border border-red-900/60 text-red-300 hover:bg-red-900/40 hover:text-red-100 transition-all flex items-center gap-1.5 text-xs font-semibold disabled:opacity-50"
              title="Clear all alerts"
            >
              {isClearing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5 text-red-400" />
              )}
              <span>Clear All</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading || isClearing}
            className="p-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-all flex items-center gap-1.5 text-xs font-medium"
            title="Refresh alerts"
          >
            <RotateCw className={`w-4 h-4 ${isLoading ? "animate-spin text-cyan-400" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-slate-800 rounded-xl bg-slate-950/40">
          <CheckCircle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-400">No community alerts logged yet.</p>
          <p className="text-xs text-slate-600 mt-1">
            Be the first to investigate a job or internship offer above!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reports.map((report) => {
            const style = badgeColors[report.risk_level] || badgeColors.LOW;
            const topRedFlag =
              report.red_flags && report.red_flags.length > 0
                ? report.red_flags[0]
                : "No severe red flags noted.";
            const isDeletingThis = deletingId === report.id;

            return (
              <div
                key={report.id}
                className="bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 p-4 rounded-xl transition-all space-y-3 relative group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}
                    >
                      {report.risk_level} ({report.risk_score}/100)
                    </span>
                    <h4 className="text-sm font-bold text-white flex items-center gap-1.5 truncate">
                      <Building className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">
                        {report.company_name || "Unverified Recruiter"}
                      </span>
                    </h4>
                  </div>

                  {/* Date & Single Delete Button */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-[11px] text-slate-500 whitespace-nowrap">
                      <Calendar className="w-3 h-3" />
                      <span>{formatDate(report.created_at)}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDelete(report.id)}
                      disabled={isDeletingThis}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/30 transition-all opacity-80 group-hover:opacity-100 disabled:opacity-40"
                      title={`Delete report #${report.id}`}
                    >
                      {isDeletingThis ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-red-400" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="text-xs text-slate-400">
                  <span className="text-slate-500 font-semibold uppercase text-[10px]">Type: </span>
                  {report.opportunity_type}
                </div>

                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800/50">
                  <span className="text-[10px] uppercase font-bold text-slate-500 block mb-0.5">
                    Primary Observation:
                  </span>
                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                    {topRedFlag}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
