export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

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
