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
    HIGH: { bg: "bg-red-950/70", text: "text-red-300", border: "border-red-800/70" },
    MEDIUM: { bg: "bg-amber-950/70", text: "text-amber-300", border: "border-amber-800/70" },
    LOW: { bg: "bg-emerald-950/70", text: "text-emerald-300", border: "border-emerald-800/70" },
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
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-slate-800/80">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            Recent Community Scam Alerts
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
            <EyeOff className="w-3.5 h-3.5 text-slate-500" />
            Anonymized reports from recent opportunity checks to keep candidates informed.
          </p>
        </div>

        {/* Action Controls: Clear All & Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {reports.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              disabled={isClearing || isLoading}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-red-900/50 text-red-400 hover:bg-red-950/60 hover:text-red-300 transition-colors flex items-center gap-1.5 text-xs font-medium disabled:opacity-50"
              title="Clear all alerts"
            >
              {isClearing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-red-400" />
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
            className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors flex items-center gap-1.5 text-xs font-medium"
            title="Refresh alerts"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-indigo-400" : "text-slate-400"}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-10 border border-dashed border-slate-800 rounded-lg bg-slate-950/40">
          <CheckCircle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-xs sm:text-sm font-medium text-slate-400">No community alerts logged yet.</p>
          <p className="text-xs text-slate-600 mt-0.5">
            Verified opportunities and fraud alerts will be displayed here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
                className="bg-slate-950 border border-slate-800 hover:border-slate-700 p-4 rounded-xl transition-colors space-y-2.5 relative group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}
                    >
                      {report.risk_level} ({report.risk_score}/100)
                    </span>
                    <h4 className="text-xs sm:text-sm font-bold text-white flex items-center gap-1.5 truncate">
                      <Building className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">
                        {report.company_name || "Unverified Recruiter"}
                      </span>
                    </h4>
                  </div>

                  {/* Date & Single Delete Button */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-[11px] text-slate-500 whitespace-nowrap">
                      <Calendar className="w-3 h-3 text-slate-500" />
                      <span>{formatDate(report.created_at)}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDelete(report.id)}
                      disabled={isDeletingThis}
                      className="p-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors opacity-80 group-hover:opacity-100 disabled:opacity-40"
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
                  <span className="font-medium text-slate-500 uppercase text-[10px]">Type: </span>
                  {report.opportunity_type}
                </div>

                <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-[10px] uppercase font-semibold text-slate-500 block mb-0.5">
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
