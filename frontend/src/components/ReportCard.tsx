"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Network,
  CheckCircle2,
  HelpCircle,
  Copy,
  Check,
  Building,
  Briefcase,
} from "lucide-react";
import { InvestigationResponse, RiskLevel } from "@/types";

interface ReportCardProps {
  data: InvestigationResponse;
  selectedLanguage: "en" | "te";
}

export const ReportCard: React.FC<ReportCardProps> = ({ data, selectedLanguage }) => {
  const { report, scam_connections, domain_analysis, student_protection, extracted_entities } =
    data;
  const [copiedQuestionIndex, setCopiedQuestionIndex] = useState<number | null>(null);

  const riskBadgeStyles: Record<
    RiskLevel,
    { badgeBg: string; text: string; border: string; barColor: string }
  > = {
    HIGH: {
      badgeBg: "bg-red-950/70",
      text: "text-red-300",
      border: "border-red-800/80",
      barColor: "bg-red-500",
    },
    MEDIUM: {
      badgeBg: "bg-amber-950/70",
      text: "text-amber-300",
      border: "border-amber-800/80",
      barColor: "bg-amber-500",
    },
    LOW: {
      badgeBg: "bg-emerald-950/70",
      text: "text-emerald-300",
      border: "border-emerald-800/80",
      barColor: "bg-emerald-500",
    },
  };

  const style = riskBadgeStyles[report.risk_level] || riskBadgeStyles.LOW;

  const handleCopyQuestion = (question: string, index: number) => {
    navigator.clipboard.writeText(question);
    setCopiedQuestionIndex(index);
    setTimeout(() => setCopiedQuestionIndex(null), 2000);
  };

  const preventiveActions =
    selectedLanguage === "te" && report.preventive_actions_te?.length
      ? report.preventive_actions_te
      : report.preventive_actions_en;

  const summary =
    selectedLanguage === "te" && report.summary_te ? report.summary_te : report.summary_en;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm space-y-6 animate-fadeIn">
      {/* Top Banner: Opportunity Header & Risk Score */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider border ${style.badgeBg} ${style.text} ${style.border}`}
            >
              {report.risk_level} Risk Opportunity
            </span>
            <span className="text-[11px] text-slate-500">Report #{data.report_id}</span>
          </div>

          <h3 className="text-lg sm:text-xl font-bold text-white flex items-center gap-2">
            {report.company_name ? (
              <>
                <Building className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>{report.company_name}</span>
              </>
            ) : (
              <span>Unverified Employer / Organization</span>
            )}
          </h3>

          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
            <Briefcase className="w-3.5 h-3.5 text-slate-500" />
            <span>Category: {report.opportunity_type}</span>
          </div>
        </div>

        {/* Score Progress Meter */}
        <div className="bg-slate-950 border border-slate-800 p-3.5 rounded-xl min-w-[200px]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Risk Score
            </span>
            <span className={`text-xl font-bold ${style.text}`}>
              {report.risk_score}
              <span className="text-xs font-normal text-slate-500">/100</span>
            </span>
          </div>
          <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden border border-slate-800/80">
            <div
              className={`h-full ${style.barColor} transition-all duration-700 ease-out`}
              style={{ width: `${Math.min(100, Math.max(5, report.risk_score))}%` }}
            />
          </div>
          <p className="text-[10px] text-slate-400 mt-1.5 text-right font-medium">
            {report.risk_score >= 75
              ? "High fraud probability"
              : report.risk_score >= 40
              ? "Moderate suspicion detected"
              : "Standard safe indicators"}
          </p>
        </div>
      </div>

      {/* Coordinated Scam Connection Network Alert */}
      {(scam_connections.is_coordinated_campaign ||
        scam_connections.matched_entities.length > 0) && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-200">
          <div className="flex items-start gap-3">
            <Network className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="space-y-1.5">
              <h4 className="text-xs sm:text-sm font-bold text-red-300 uppercase tracking-wide">
                Coordinated Scam Pattern Detected
              </h4>
              <p className="text-xs text-red-200/90 leading-relaxed">
                One or more contact identifiers in this opportunity match previously flagged fraud reports in our database.
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {scam_connections.matched_entities.map((entity, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono bg-red-900/40 border border-red-800 text-red-200"
                  >
                    <span className="uppercase text-[10px] font-semibold text-red-300">
                      {entity.entity_type}:
                    </span>
                    <span>{entity.entity_value}</span>
                    <span className="bg-red-950 px-1 rounded text-[10px] text-red-300 border border-red-800/60 font-sans">
                      {entity.previous_reports} reports
                    </span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary Section */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 sm:p-5">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center justify-between">
          <span>
            {selectedLanguage === "te" ? "Tenglish Summary" : "Investigation Summary"}
          </span>
          <span className="text-[10px] font-medium text-indigo-400 uppercase">
            {selectedLanguage === "te" ? "Tenglish" : "English"}
          </span>
        </h4>
        <p className="text-xs sm:text-sm text-slate-200 leading-relaxed whitespace-pre-line">{summary}</p>
      </div>

      {/* Two Column Section: Red Flags & Student Protection Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Red Flags */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Detected Red Flags ({report.red_flags.length})
          </h4>
          <ul className="space-y-2">
            {report.red_flags.map((flag, i) => (
              <li
                key={i}
                className="text-xs text-slate-300 flex items-start gap-2.5 bg-slate-900/90 p-2.5 rounded-lg border border-slate-800/80"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Student Protection Alerts */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-red-400 flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            Student Protection Alerts ({report.student_protection_alerts.length})
          </h4>
          {report.student_protection_alerts.length > 0 ? (
            <ul className="space-y-2">
              {report.student_protection_alerts.map((alert, i) => (
                <li
                  key={i}
                  className="text-xs text-red-200 flex items-start gap-2 bg-red-950/30 p-2.5 rounded-lg border border-red-900/40"
                >
                  <AlertOctagon className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                  <span>{alert}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-300 flex items-center gap-2 bg-emerald-950/20 p-2.5 rounded-lg border border-emerald-900/40 font-medium">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              No upfront payment or sensitive personal data demands detected.
            </p>
          )}
        </div>
      </div>

      {/* Preventive Actions */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
          {selectedLanguage === "te"
            ? "Recommended Safety Steps (Tenglish)"
            : "Recommended Safety Steps"}
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {preventiveActions.map((action, i) => (
            <div
              key={i}
              className="text-xs text-slate-300 flex items-start gap-2 bg-slate-900/90 p-2.5 rounded-lg border border-slate-800/80"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
              <span>{action}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recruiter Verification Questions */}
      {report.verification_questions && report.verification_questions.length > 0 && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
              <HelpCircle className="w-4 h-4 text-indigo-400" />
              Recruiter Verification Questions
            </h4>
            <span className="text-[11px] text-slate-500">Copy & send to test recruiter validity</span>
          </div>

          <div className="space-y-2">
            {report.verification_questions.map((question, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 bg-slate-900/90 border border-slate-800/80 p-2.5 rounded-lg text-xs text-slate-200"
              >
                <div className="flex items-start gap-2">
                  <span className="font-bold text-indigo-400 text-xs">Q{i + 1}.</span>
                  <span>{question}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopyQuestion(question, i)}
                  className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0"
                  title="Copy question"
                >
                  {copiedQuestionIndex === i ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400 text-[11px]">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-[11px]">Copy</span>
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
