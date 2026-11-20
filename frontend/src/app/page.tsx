"use client";

import React, { useState, useEffect, useRef } from "react";
import { Header } from "@/components/Header";
import { InvestigatorForm } from "@/components/InvestigatorForm";
import { ReportCard } from "@/components/ReportCard";
import { RecentAlerts } from "@/components/RecentAlerts";
import { FollowUpModal } from "@/components/FollowUpModal";
import { API_BASE_URL, fetchReportById } from "@/lib/api";
import {
  StatsResponse,
  OpportunityReportItem,
  InvestigationResponse,
} from "@/types";
import { AlertCircle } from "lucide-react";

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);

  const [reports, setReports] = useState<OpportunityReportItem[]>([]);
  const [loadingReports, setLoadingReports] = useState<boolean>(true);

  const [investigationResult, setInvestigationResult] =
    useState<InvestigationResponse | null>(null);
  const [isInvestigating, setIsInvestigating] = useState<boolean>(false);
  const [investigationError, setInvestigationError] = useState<string | null>(null);

  const [selectedLanguage, setSelectedLanguage] = useState<"en" | "te">("en");
  const [isFollowUpOpen, setIsFollowUpOpen] = useState<boolean>(false);

  const reportCardRef = useRef<HTMLDivElement>(null);

  // Fetch Live Platform Stats
  const fetchStats = async () => {
    try {
      setLoadingStats(true);
      const res = await fetch(`${API_BASE_URL}/api/stats`);
      if (res.ok) {
        const data: StatsResponse = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.warn("Failed to fetch live stats from backend:", err);
    } finally {
      setLoadingStats(false);
    }
  };

  // Fetch Recent Community Reports
  const fetchReports = async () => {
    try {
      setLoadingReports(true);
      const res = await fetch(`${API_BASE_URL}/api/reports`);
      if (res.ok) {
        const data: OpportunityReportItem[] = await res.json();
        setReports(data);
      }
    } catch (err) {
      console.warn("Failed to fetch reports from backend:", err);
    } finally {
      setLoadingReports(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchReports();
  }, []);

  // Handle Opportunity Submission
  const handleInvestigate = async (formData: FormData) => {
    setIsInvestigating(true);
    setInvestigationError(null);
    setInvestigationResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/investigate`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let errorDetail = "Failed to complete verification. Please try again.";
        try {
          const errorJson = await response.json();
          if (errorJson.detail) {
            errorDetail =
              typeof errorJson.detail === "string"
                ? errorJson.detail
                : JSON.stringify(errorJson.detail);
          }
        } catch {
          // fallback error detail
        }
        throw new Error(errorDetail);
      }

      const result: InvestigationResponse = await response.json();
      setInvestigationResult(result);

      // Auto-refresh stats and reports in background
      fetchStats();
      fetchReports();

      // Smooth scroll to report card
      setTimeout(() => {
        reportCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err: any) {
      setInvestigationError(
        err.message ||
          "Network error: Unable to contact ScamShield backend at " + API_BASE_URL
      );
    } finally {
      setIsInvestigating(false);
    }
  };

  // View Full Investigation Report for a clicked Community Alert
  const handleSelectReport = async (reportId: number) => {
    try {
      setInvestigationError(null);
      const data = await fetchReportById(reportId);
      setInvestigationResult(data);
      setTimeout(() => {
        reportCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Failed to load report #${reportId}`;
      setInvestigationError(msg);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1120] text-slate-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white">
      {/* Top Navigation Bar with Hamburger Drawer Trigger */}
      <Header
        stats={stats}
        loadingStats={loadingStats}
        hasActiveReport={!!investigationResult}
        onOpenFollowUp={() => setIsFollowUpOpen(true)}
      />

      {/* Main Workspace (Full-Width Clean Dashboard Layout) */}
      <main className="flex-1 w-full px-4 sm:px-6 lg:px-10 py-6 sm:py-8 space-y-8 sm:space-y-10">
        {/* Global Error Banner */}
        {investigationError && (
          <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-red-200 text-xs sm:text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">Verification Request Failed</p>
              <p className="text-xs text-red-300 mt-0.5">{investigationError}</p>
            </div>
          </div>
        )}

        {/* Top Section: InvestigatorForm */}
        <InvestigatorForm
          onInvestigate={handleInvestigate}
          isLoading={isInvestigating}
          selectedLanguage={selectedLanguage}
          onLanguageChange={setSelectedLanguage}
        />

        {/* Middle Section: ReportCard (dynamically displayed when a report exists) */}
        {investigationResult && (
          <div ref={reportCardRef} className="animate-fadeIn">
            <ReportCard
              data={investigationResult}
              selectedLanguage={selectedLanguage}
            />
          </div>
        )}

        {/* Bottom Section: Recent Community Alerts */}
        <RecentAlerts
          reports={reports}
          isLoading={loadingReports}
          onRefresh={fetchReports}
          onReportsChanged={() => {
            fetchReports();
            fetchStats();
          }}
          onSelectReport={handleSelectReport}
        />

        {/* Clean Dashboard Footer */}
        <footer className="pt-6 border-t border-slate-800/60 text-center text-xs text-slate-500">
          <p className="text-slate-400 font-medium">
            ScamShield — Career Opportunity Safety & Verification Dashboard
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            An open platform protecting students and candidates against recruitment fraud.
          </p>
        </footer>
      </main>

      {/* Follow-Up Assistant Chat Modal / Drawer */}
      <FollowUpModal
        isOpen={isFollowUpOpen}
        onClose={() => setIsFollowUpOpen(false)}
        data={investigationResult}
        selectedLanguage={selectedLanguage}
        onLanguageChange={setSelectedLanguage}
      />
    </div>
  );
}
