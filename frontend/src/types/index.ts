export type OpportunityType =
  | "Job"
  | "Internship"
  | "Work From Home"
  | "Freelancing"
  | "Training Program"
  | "Placement Drive";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface MatchedEntity {
  entity_type: string;
  entity_value: string;
  previous_reports: number;
}

export interface ScamConnections {
  matched_entities: MatchedEntity[];
  total_connected_reports: number;
  is_coordinated_campaign: boolean;
}

export interface DomainAnalysis {
  free_provider_warnings: string[];
  suspicious_tld_warnings: string[];
  hyphenated_domain_warnings: string[];
  flags: string[];
  has_suspicious_domain: boolean;
}

export interface StudentProtection {
  pii_alerts: string[];
  payment_alerts: string[];
  has_critical_risk: boolean;
  all_alerts: string[];
}

export interface ExtractedEntities {
  phone: string[];
  email: string[];
  domain: string[];
  upi_id: string[];
  telegram: string[];
}

export interface InvestigationReportData {
  opportunity_type: string;
  company_name: string | null;
  risk_level: RiskLevel;
  risk_score: number;
  red_flags: string[];
  student_protection_alerts: string[];
  summary_en: string;
  summary_te: string;
  preventive_actions_en: string[];
  preventive_actions_te: string[];
  verification_questions: string[];
}

export interface InvestigationResponse {
  report_id: number;
  created_at: string | null;
  report: InvestigationReportData;
  scam_connections: ScamConnections;
  domain_analysis: DomainAnalysis;
  student_protection: StudentProtection;
  extracted_entities: ExtractedEntities;
}

export interface OpportunityReportItem {
  id: number;
  opportunity_type: string;
  company_name: string | null;
  risk_level: RiskLevel;
  risk_score: number;
  summary_en: string;
  summary_te: string;
  red_flags: string[];
  created_at: string | null;
}

export interface StatsResponse {
  total_investigations: number;
  safe_count: number;
  high_risk_count: number;
  coordinated_campaigns_count: number;
}

export type FollowUpVerdict = "STILL_HIGH_RISK" | "SUSPICIOUS" | "LOOKS_LEGIT";
export type FollowUpIntent = "CASUAL_CHAT" | "STUDENT_QUESTION" | "RECRUITER_REPLY";

export interface FollowUpRequestPayload {
  report_id: number;
  message: string;
  language: "en" | "te";
  verification_questions?: string[];
  chat_history: { role: string; content: string }[];
  file?: File | null;
}

export interface FollowUpResponseData {
  message_intent?: FollowUpIntent;
  matched_question?: string | null;
  verdict?: FollowUpVerdict | null;
  analysis: string;
  suggested_reply?: string | null;
  has_critical_risk?: boolean;
}

export interface FollowUpChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachment_name?: string | null;
  message_intent?: FollowUpIntent;
  matched_question?: string | null;
  verdict?: FollowUpVerdict | null;
  suggested_reply?: string | null;
  has_critical_risk?: boolean;
  timestamp: string;
}
