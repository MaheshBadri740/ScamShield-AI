"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileText,
  FileImage,
  X,
  Search,
  Loader2,
  AlertCircle,
  Languages,
  Shield,
  Sparkles,
} from "lucide-react";
import { OpportunityType } from "@/types";

interface InvestigatorFormProps {
  onInvestigate: (formData: FormData) => Promise<void>;
  isLoading: boolean;
  selectedLanguage: "en" | "te";
  onLanguageChange: (lang: "en" | "te") => void;
}

const OPPORTUNITY_TYPES: OpportunityType[] = [
  "Job",
  "Internship",
  "Work From Home",
  "Freelancing",
  "Training Program",
  "Placement Drive",
];

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

export const InvestigatorForm: React.FC<InvestigatorFormProps> = ({
  onInvestigate,
  isLoading,
  selectedLanguage,
  onLanguageChange,
}) => {
  const [opportunityType, setOpportunityType] = useState<OpportunityType>("Job");
  const [text, setText] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (incomingFile: File | null) => {
    setValidationError(null);
    if (!incomingFile) return;

    if (incomingFile.size > MAX_FILE_SIZE) {
      setValidationError("File exceeds 5MB limit. Please upload a smaller file.");
      return;
    }

    const validExtensions = ["png", "jpg", "jpeg", "webp", "pdf"];
    const ext = incomingFile.name.split(".").pop()?.toLowerCase();
    if (!ext || !validExtensions.includes(ext)) {
      setValidationError("Invalid file type. Supported formats: PNG, JPG, JPEG, WEBP, PDF.");
      return;
    }

    setFile(incomingFile);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const clearFile = () => {
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!text.trim() && !file) {
      setValidationError(
        "Please paste opportunity text or upload a document/screenshot to investigate."
      );
      return;
    }

    const formData = new FormData();
    if (text.trim()) {
      formData.append("text", text.trim());
    }
    formData.append("opportunity_type", opportunityType);
    if (file) {
      formData.append("file", file);
    }

    await onInvestigate(formData);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl shadow-cyan-950/10">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-cyan-400" />
            AI Opportunity Forensic Scanner
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Submit suspicious job offers, WhatsApp messages, or offer letters for real-time fraud analysis.
          </p>
        </div>

        {/* Language Toggle */}
        <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
          <Languages className="w-4 h-4 text-slate-400 ml-2" />
          <button
            type="button"
            onClick={() => onLanguageChange("en")}
            className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
              selectedLanguage === "en"
                ? "bg-cyan-500 text-white shadow-md shadow-cyan-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            English
          </button>
          <button
            type="button"
            onClick={() => onLanguageChange("te")}
            className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
              selectedLanguage === "te"
                ? "bg-cyan-500 text-white shadow-md shadow-cyan-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Tenglish
          </button>
        </div>
      </div>

      {validationError && (
        <div className="mb-6 p-4 rounded-xl bg-red-950/60 border border-red-800/80 text-red-200 text-xs sm:text-sm flex items-start gap-3 animate-fadeIn">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>{validationError}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Opportunity Type */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Opportunity Category
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {OPPORTUNITY_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setOpportunityType(type)}
                className={`px-3 py-2.5 rounded-xl text-xs sm:text-sm font-medium border text-left transition-all ${
                  opportunityType === type
                    ? "bg-cyan-950/70 border-cyan-500 text-cyan-300 shadow-sm shadow-cyan-500/20"
                    : "bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300"
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Text Area */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Job / Internship Description or Recruiter Messages
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste recruiter email, WhatsApp/Telegram messages, promised stipend, training fee demands, or job description here..."
            rows={5}
            className="w-full rounded-xl bg-slate-950/90 border border-slate-800 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-slate-200 placeholder-slate-500 text-sm p-4 transition-all resize-y outline-none"
          />
        </div>

        {/* File Upload (Drag & Drop) */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Offer Letter or Screenshot Upload (Optional)
          </label>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer ${
              dragOver
                ? "border-cyan-400 bg-cyan-950/20"
                : file
                ? "border-emerald-600/70 bg-emerald-950/10"
                : "border-slate-800 bg-slate-950/40 hover:border-slate-700"
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileChange(e.target.files[0]);
                }
              }}
            />

            {file ? (
              <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-3 rounded-lg max-w-md mx-auto">
                <div className="flex items-center gap-3 overflow-hidden text-left">
                  {file.name.endsWith(".pdf") ? (
                    <FileText className="w-8 h-8 text-red-400 shrink-0" />
                  ) : (
                    <FileImage className="w-8 h-8 text-cyan-400 shrink-0" />
                  )}
                  <div className="truncate">
                    <p className="text-sm font-semibold text-slate-200 truncate">{file.name}</p>
                    <p className="text-xs text-slate-400">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    clearFile();
                  }}
                  className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <UploadCloud className="w-8 h-8 text-cyan-400 mx-auto" />
                <p className="text-sm text-slate-300 font-medium">
                  Click or drag & drop offer letter or chat screenshot
                </p>
                <p className="text-xs text-slate-500">
                  Supported: PNG, JPG, JPEG, WEBP, PDF (Max 5MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Submit Button */}
        <div>
          <button
            type="submit"
            disabled={isLoading}
            className={`w-full py-3.5 px-6 rounded-xl font-bold text-sm tracking-wide text-white transition-all shadow-lg flex items-center justify-center gap-2 ${
              isLoading
                ? "bg-cyan-800 cursor-not-allowed opacity-80"
                : "bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 shadow-cyan-500/25 active:scale-[0.99]"
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Verifying Opportunity & Checking Scam Signals...</span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                <span>Investigate Career Opportunity</span>
                <Sparkles className="w-4 h-4 text-cyan-200" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
