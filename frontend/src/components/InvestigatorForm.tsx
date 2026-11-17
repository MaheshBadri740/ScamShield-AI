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
  ShieldCheck,
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
        "Please paste opportunity text or upload a document/screenshot to verify."
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
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 sm:p-8 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 pb-5 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-indigo-400 shrink-0" />
            Verify Job or Internship Offer
          </h2>
          <p className="text-sm sm:text-base text-slate-400 mt-1">
            Paste a recruiter message or upload an offer letter to verify if it is safe.
          </p>
        </div>

        {/* Language Toggle */}
        <div className="flex items-center gap-1 bg-slate-950 p-1.5 rounded-xl border border-slate-800 self-start sm:self-auto shrink-0">
          <Languages className="w-4 h-4 text-slate-400 ml-1.5 mr-1" />
          <button
            type="button"
            onClick={() => onLanguageChange("en")}
            className={`px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg transition-all ${
              selectedLanguage === "en"
                ? "bg-slate-800 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            English
          </button>
          <button
            type="button"
            onClick={() => onLanguageChange("te")}
            className={`px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg transition-all ${
              selectedLanguage === "te"
                ? "bg-slate-800 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Tenglish
          </button>
        </div>
      </div>

      {validationError && (
        <div className="mb-5 p-3 rounded-lg bg-red-950/70 border border-red-800 text-red-200 text-xs flex items-start gap-2.5 animate-fadeIn">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5 sm:space-y-6">
        {/* Opportunity Category */}
        <div>
          <label className="block text-xs sm:text-sm font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
            Opportunity Category
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 sm:gap-3 w-full">
            {OPPORTUNITY_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setOpportunityType(type)}
                className={`px-3 py-3 rounded-xl text-sm font-medium border text-center transition-all ${
                  opportunityType === type
                    ? "bg-indigo-950/60 border-indigo-500/80 text-indigo-300 font-semibold shadow-xs"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Text Area */}
        <div>
          <label className="block text-xs sm:text-sm font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
            Job / Internship Description or Recruiter Messages
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste recruiter email, WhatsApp/Telegram messages, promised stipend, training fee demands, or job description here..."
            rows={5}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-slate-200 placeholder-slate-500 text-sm p-4 transition-all resize-y outline-none leading-relaxed"
          />
        </div>

        {/* File Upload (Drag & Drop) */}
        <div>
          <label className="block text-xs sm:text-sm font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
            Offer Letter or Screenshot Upload (Optional)
          </label>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`w-full border-2 border-dashed rounded-xl p-6 sm:p-8 text-center transition-colors cursor-pointer ${
              dragOver
                ? "border-indigo-500 bg-indigo-950/30"
                : file
                ? "border-emerald-500/70 bg-emerald-950/20"
                : "border-slate-800 bg-slate-950/50 hover:bg-slate-950 hover:border-slate-700"
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
              <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-3.5 rounded-xl max-w-xl mx-auto shadow-sm">
                <div className="flex items-center gap-3 overflow-hidden text-left">
                  {file.name.endsWith(".pdf") ? (
                    <FileText className="w-7 h-7 text-red-400 shrink-0" />
                  ) : (
                    <FileImage className="w-7 h-7 text-indigo-400 shrink-0" />
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
                  className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <UploadCloud className="w-7 h-7 text-slate-400 mx-auto" />
                <p className="text-sm sm:text-base text-slate-300 font-medium">
                  Click or drag & drop offer letter or screenshot
                </p>
                <p className="text-xs text-slate-500">
                  PNG, JPG, JPEG, WEBP, or PDF (Max 5MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Submit Button: Solid Professional Indigo */}
        <div>
          <button
            type="submit"
            disabled={isLoading}
            className={`w-full py-3.5 sm:py-4 px-6 rounded-xl font-semibold text-base text-white transition-colors flex items-center justify-center gap-2.5 shadow-md ${
              isLoading
                ? "bg-indigo-900/80 text-indigo-300 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700"
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin text-white" />
                <span>Verifying Opportunity & Checking Scam Signals...</span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                <span>Verify Opportunity</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
