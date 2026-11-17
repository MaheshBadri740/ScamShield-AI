"use client";

import React, { useState, useEffect, useRef } from "react";
import { Header } from "@/components/Header";
import { InvestigatorForm } from "@/components/InvestigatorForm";
import { ReportCard } from "@/components/ReportCard";
import { RecentAlerts } from "@/components/RecentAlerts";
import { API_BASE_URL } from "@/lib/api";
import {
  StatsResponse,
  OpportunityReportItem,
  InvestigationResponse,
} from "@/types";
import { AlertCircle, Shield, Sparkles, CheckCircle2 } from "lucide-react";

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
        let errorDetail = "Failed to complete investigation. Please try again.";
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
          "Network error: Unable to contact ScamShield AI backend at " + API_BASE_URL
      );
    } finally {
      setIsInvestigating(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white">
      {/* Navigation Header & Stats Bar */}
      <Header stats={stats} loadingStats={loadingStats} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-10">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Student Career Safety & Verification Platform</span>
          </div>

          <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white leading-tight">
            Verify Every Opportunity. <br />
            <span className="bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-400 bg-clip-text text-transparent">
              Protect Your Future.
            </span>
          </h2>

          <p className="text-sm sm:text-base text-slate-400 leading-relaxed max-w-2xl mx-auto">
            Safeguard your career from fake internships, upfront registration fee traps, and
            identity harvesting syndicates with multimodal AI intelligence.
          </p>
        </div>

        {/* Global Error Banner */}
        {investigationError && (
          <div className="p-4 rounded-xl bg-red-950/70 border border-red-700 text-red-200 text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-bold">Investigation Failed</p>
              <p className="text-xs text-red-300 mt-0.5">{investigationError}</p>
            </div>
          </div>
        )}

        {/* Investigator Input Form */}
        <InvestigatorForm
          onInvestigate={handleInvestigate}
          isLoading={isInvestigating}
          selectedLanguage={selectedLanguage}
          onLanguageChange={setSelectedLanguage}
        />

        {/* Dynamic Investigation Report Card */}
        {investigationResult && (
          <div ref={reportCardRef} className="pt-4 animate-fadeIn">
            <div className="flex items-center gap-2 mb-4 text-emerald-400 text-sm font-bold">
              <CheckCircle2 className="w-5 h-5" />
              <span>Investigation Complete</span>
            </div>
            <ReportCard data={investigationResult} selectedLanguage={selectedLanguage} />
          </div>
        )}

        {/* Recent Community Alerts */}
        <RecentAlerts
          reports={reports}
          isLoading={loadingReports}
          onRefresh={fetchReports}
          onReportsChanged={() => {
            fetchReports();
            fetchStats();
          }}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/90 py-8 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 space-y-2">
          <p className="font-semibold text-slate-400">
            ScamShield AI — Student Protection & Career Opportunity Defense Platform
          </p>
          <p>
            An open initiative protecting college students and early-career candidates from predatory recruitment fraud.
          </p>
        </div>
      </footer>
    </div>
  );
}
