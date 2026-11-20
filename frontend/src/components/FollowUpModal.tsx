"use client";

import React, { useState, useEffect } from "react";
import {
  MessageSquare,
  MessageSquareText,
  X,
  Send,
  Loader2,
  RotateCcw,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Copy,
  Check,
  Building,
  Briefcase,
  Languages,
} from "lucide-react";
import {
  InvestigationResponse,
  FollowUpChatMessage,
  FollowUpVerdict,
} from "@/types";
import { sendFollowUp } from "@/lib/api";

interface FollowUpModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: InvestigationResponse | null;
  selectedLanguage: "en" | "te";
  onLanguageChange?: (lang: "en" | "te") => void;
}

export const FollowUpModal: React.FC<FollowUpModalProps> = ({
  isOpen,
  onClose,
  data,
  selectedLanguage,
  onLanguageChange,
}) => {
  const [messages, setMessages] = useState<FollowUpChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedReplyId, setCopiedReplyId] = useState<string | null>(null);

  // Reset messages when report changes
  useEffect(() => {
    setMessages([]);
    setInputMessage("");
    setError(null);
  }, [data?.report_id]);

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !data) return null;

  const { report } = data;

  const followUpVerdictConfig: Record<
    FollowUpVerdict,
    { labelEn: string; labelTe: string; bg: string; text: string; border: string; icon: React.ReactNode }
  > = {
    STILL_HIGH_RISK: {
      labelEn: "Still High Risk / Scam",
      labelTe: "Still High Risk / Scam (Dabbu Kattavaddu)",
      bg: "bg-red-950/80",
      text: "text-red-300",
      border: "border-red-800/80",
      icon: <AlertOctagon className="w-3.5 h-3.5 text-red-400 shrink-0" />,
    },
    SUSPICIOUS: {
      labelEn: "Suspicious Reply",
      labelTe: "Suspicious Reply (Caution)",
      bg: "bg-amber-950/80",
      text: "text-amber-300",
      border: "border-amber-800/80",
      icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />,
    },
    LOOKS_LEGIT: {
      labelEn: "Looks Reasonable",
      labelTe: "Looks Reasonable (Standard Verification)",
      bg: "bg-emerald-950/80",
      text: "text-emerald-300",
      border: "border-emerald-800/80",
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />,
    },
  };

  const handleCopyReply = (reply: string, id: string) => {
    navigator.clipboard.writeText(reply);
    setCopiedReplyId(id);
    setTimeout(() => setCopiedReplyId(null), 2000);
  };

  const handleSendFollowUp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || isSending) return;

    const userMsg: FollowUpChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInputMessage("");
    setIsSending(true);
    setError(null);

    try {
      const historyPayload = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await sendFollowUp({
        report_id: data.report_id,
        message: trimmed,
        language: selectedLanguage,
        verification_questions: report.verification_questions || [],
        chat_history: historyPayload,
      });

      const assistantMsg: FollowUpChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: res.analysis,
        message_intent: res.message_intent,
        matched_question: res.matched_question,
        verdict: res.verdict,
        suggested_reply: res.suggested_reply,
        has_critical_risk: res.has_critical_risk,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to analyze response";
      setError(msg);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-5 animate-fadeIn">
      {/* Click outside backdrop to close */}
      <div
        className="fixed inset-0 -z-10"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Card */}
      <div
        className="w-full max-w-3xl bg-[#0F172A] border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[92vh] overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800/90 bg-slate-900/60 flex items-start justify-between gap-4 shrink-0">
          <div className="flex items-start gap-3 min-w-0">
            <img
              src="/assistant-icon.jpg"
              alt="Follow-Up Assistant"
              className="w-9 h-9 rounded-lg object-cover border border-indigo-500/30 shrink-0 mt-0.5"
            />
            <div className="space-y-1.5 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-indigo-950/80 border border-indigo-700/80 text-indigo-300">
                  Follow-Up Assistant
                </span>
                <span className="text-[11px] text-slate-500">Report #{data.report_id}</span>
                {onLanguageChange ? (
                  <div className="inline-flex items-center bg-slate-950/90 p-0.5 rounded-lg border border-slate-800 text-[11px] shrink-0">
                    <Languages className="w-3 h-3 text-slate-400 ml-1.5 mr-1" />
                    <button
                      type="button"
                      onClick={() => onLanguageChange("en")}
                      className={`px-2 py-0.5 rounded-md font-medium transition-all ${
                        selectedLanguage === "en"
                          ? "bg-slate-800 text-white font-semibold shadow-xs"
                          : "text-slate-400 hover:text-white"
                      }`}
                      title="Switch to English"
                    >
                      English
                    </button>
                    <button
                      type="button"
                      onClick={() => onLanguageChange("te")}
                      className={`px-2 py-0.5 rounded-md font-medium transition-all ${
                        selectedLanguage === "te"
                          ? "bg-slate-800 text-white font-semibold shadow-xs"
                          : "text-slate-400 hover:text-white"
                      }`}
                      title="Switch to Tenglish"
                    >
                      Tenglish
                    </button>
                  </div>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                    {selectedLanguage === "te" ? "Tenglish Mode" : "English Mode"}
                  </span>
                )}
              </div>

              <h3 id="modal-title" className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                <Building className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>{report.company_name || "Unverified Recruiter"}</span>
                <span className="text-xs text-slate-400 font-normal">({report.opportunity_type})</span>
              </h3>

              <p className="text-xs text-slate-400">
                {selectedLanguage === "te"
                  ? "Ee offer gurinchi doubt unte adagandi leda recruiter reply ni ikkada paste cheyandi."
                  : "Ask a question about this offer or paste a recruiter's reply to check."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {messages.length > 0 && (
              <button
                type="button"
                onClick={() => setMessages([])}
                className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/80 hover:bg-slate-700 transition-colors"
                title="Clear conversation"
              >
                <RotateCcw className="w-3 h-3" />
                <span className="hidden sm:inline">Clear Chat</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 transition-colors"
              aria-label="Close modal"
              title="Close (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body: Message History */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {messages.length === 0 ? (
            <div className="bg-slate-900/60 border border-dashed border-slate-800 rounded-2xl p-6 text-center space-y-3 my-auto">
              <div className="w-12 h-12 rounded-full bg-indigo-950/60 border border-indigo-800/80 flex items-center justify-center mx-auto text-indigo-400">
                <MessageSquareText className="w-6 h-6" />
              </div>

              <div className="space-y-1 max-w-md mx-auto">
                <h4 className="text-sm font-semibold text-white">
                  {selectedLanguage === "te"
                    ? "Follow-Up & Safety Advisor"
                    : "Follow-Up & Safety Advisor"}
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {selectedLanguage === "te"
                    ? "Recruiter ichina reply ikkada paste cheyandi leda ee job offer gurinchi emaina doubts unte adagandi."
                    : "Paste a recruiter's response or email, ask for career advice, or ask questions about this offer."}
                </p>
              </div>

              {report.verification_questions && report.verification_questions.length > 0 && (
                <div className="pt-3 border-t border-slate-800/60 text-left max-w-lg mx-auto">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center gap-1.5">
                    <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Reference: Questions you asked this recruiter</span>
                  </p>
                  <ul className="space-y-1 text-xs text-slate-400">
                    {report.verification_questions.map((q, i) => (
                      <li key={i} className="flex items-start gap-1.5 bg-slate-950/60 p-2 rounded border border-slate-800/60">
                        <span className="text-indigo-400 font-bold shrink-0">Q{i + 1}.</span>
                        <span className="line-clamp-2">{q}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => {
                if (msg.role === "user") {
                  return (
                    <div key={msg.id} className="flex justify-end">
                      <div className="bg-indigo-600/20 border border-indigo-500/30 text-indigo-100 rounded-2xl rounded-tr-sm p-3.5 text-xs max-w-[88%] sm:max-w-[78%] space-y-1 shadow-xs">
                        <div className="flex items-center justify-between gap-3 text-[10px] text-indigo-300/80 font-medium">
                          <span>You</span>
                          <span>{msg.timestamp}</span>
                        </div>
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      </div>
                    </div>
                  );
                }

                const verdictCfg = msg.verdict
                  ? followUpVerdictConfig[msg.verdict]
                  : null;

                return (
                  <div key={msg.id} className="flex justify-start">
                    <div className="bg-slate-900/95 border border-slate-800 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-200 max-w-[95%] sm:max-w-[90%] space-y-3 shadow-md">
                      {/* Top bar with verdict or intent badge and timestamp */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        {verdictCfg ? (
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${verdictCfg.bg} ${verdictCfg.text} ${verdictCfg.border}`}
                          >
                            {verdictCfg.icon}
                            <span>
                              {selectedLanguage === "te"
                                ? verdictCfg.labelTe
                                : verdictCfg.labelEn}
                            </span>
                          </span>
                        ) : msg.message_intent === "STUDENT_QUESTION" ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border bg-indigo-950/70 text-indigo-300 border-indigo-800/80">
                            <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                            <span>Advisor Guidance</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-800/80 text-slate-300 border border-slate-700/60">
                            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                            <span>ScamShield Assistant</span>
                          </span>
                        )}
                        <span className="text-[10px] text-slate-500">{msg.timestamp}</span>
                      </div>

                      {/* Matched Question Badge */}
                      {msg.matched_question && (
                        <div className="flex items-center gap-1.5 text-[11px] font-medium text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-2.5 py-1 rounded-md w-fit">
                          <HelpCircle className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          <span>Matched Question: {msg.matched_question}</span>
                        </div>
                      )}

                      {/* Forensic / Advisory Analysis */}
                      <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>

                      {/* Suggested Reply Box */}
                      {msg.suggested_reply && (
                        <div className="bg-slate-950/80 border border-slate-800/90 rounded-lg p-3 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
                              {msg.verdict === "STILL_HIGH_RISK"
                                ? "Recommended Action:"
                                : msg.message_intent === "STUDENT_QUESTION"
                                ? "Suggested Response Template (English):"
                                : "Suggested Reply to Recruiter (English):"}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopyReply(msg.suggested_reply!, msg.id)}
                              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-medium flex items-center gap-1 transition-colors"
                            >
                              {copiedReplyId === msg.id ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  <span className="text-emerald-400">Copied</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3 text-slate-400" />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                          <div className="bg-slate-900/80 border border-slate-800/80 p-2.5 rounded text-xs text-slate-300 leading-relaxed font-sans select-all">
                            {msg.suggested_reply}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isSending && (
                <div className="flex justify-start">
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm p-3.5 text-xs text-slate-300 flex items-center gap-2.5 shadow-sm">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                    <span>Thinking...</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error banner if any */}
        {error && (
          <div className="px-5 py-2.5 text-xs text-red-300 bg-red-950/50 border-t border-red-900/80 flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Modal Footer / Input Form */}
        <div className="p-4 border-t border-slate-800/90 bg-slate-900/60 shrink-0">
          <form onSubmit={handleSendFollowUp} className="flex gap-2 items-end">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendFollowUp();
                }
              }}
              placeholder={
                selectedLanguage === "te"
                  ? "Recruiter reply paste cheyandi, leda emaina doubt adagandi..."
                  : "Ask a question (e.g. 'Should I share my resume?') or paste a recruiter's reply..."
              }
              rows={2}
              className="flex-1 bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none resize-none transition-colors"
            />

            <button
              type="submit"
              disabled={isSending || !inputMessage.trim()}
              className="h-[46px] px-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-1.5 transition-colors shrink-0"
            >
              {isSending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Analyze</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
