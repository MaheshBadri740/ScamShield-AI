import {
  FollowUpRequestPayload,
  FollowUpResponseData,
  InvestigationResponse,
} from "@/types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function fetchReportById(
  reportId: number
): Promise<InvestigationResponse> {
  const res = await fetch(`${API_BASE_URL}/api/reports/${reportId}`);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Failed to fetch report #${reportId}`);
  }
  return await res.json();
}

export async function sendFollowUp(
  payload: FollowUpRequestPayload
): Promise<FollowUpResponseData> {
  const formData = new FormData();
  formData.append("report_id", payload.report_id.toString());
  formData.append("message", payload.message || "");
  formData.append("language", payload.language || "en");
  formData.append("chat_history", JSON.stringify(payload.chat_history || []));
  formData.append(
    "verification_questions",
    JSON.stringify(payload.verification_questions || [])
  );
  if (payload.file) {
    formData.append("file", payload.file);
  }

  const res = await fetch(`${API_BASE_URL}/api/investigate/followup`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Server error: ${res.status}`);
  }

  return await res.json();
}

export async function deleteReport(reportId: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports/${reportId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch (err) {
    console.error(`Failed to delete report #${reportId}:`, err);
    return false;
  }
}

export async function clearAllReports(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports`, {
      method: "DELETE",
    });
    return res.ok;
  } catch (err) {
    console.error("Failed to clear all reports:", err);
    return false;
  }
}
