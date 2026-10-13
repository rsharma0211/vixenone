export type FindingStatus = 'Compliant' | 'Partially compliant' | 'Non-compliant' | 'Not evidenced';
export type RiskType = 'Exclusion' | 'Ambiguity' | 'Unknown cost' | 'Contradiction' | 'Omission';
export type Severity = 'High' | 'Medium' | 'Low';
export type LifecycleStatusType = 'Draft' | 'Requirements review' | 'Analysed' | 'Stale' | 'Ready' | 'Processing' | 'Error';
export type JobStatus = 'queued' | 'extracting' | 'analysing' | 'done' | 'failed';

export interface AnalysisJob {
  id: string;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  progress_step_label: string;
}

export interface Evaluation {
  id: string;
  name: string;
  name_short: string;
  category: string;
  contract_type: string;
  total_requirements: number;
  mandatory_requirements: number;
  vendors_count: number;
  updated_at: string;
  lifecycle_status: LifecycleStatusType;
  latest_job: AnalysisJob | null;
}

export interface Vendor {
  id: string;
  name: string;
  tag?: string;
  score: number;
  mandatory_failures: number;
  monthly_base_inr: number;
  gst_rate: number;
  monthly_gst_inr: number;
  monthly_total_inr: number;
  unknown_costs_count: number;
  needs_review_count: number;
}

export interface Requirement {
  id: string;
  code: string;
  text: string;
  category: string;
  mandatory: boolean;
  acceptance_condition: string;
  source: string;
}

export interface Evidence {
  quote: string;
  highlight?: string;
  document: string;
  page: number;
  section: string;
}

export interface Finding {
  requirement_id: string;
  vendor_id: string;
  status: FindingStatus;
  needs_review: boolean;
  inferred: boolean;
  risk_types: RiskType[];
  severity?: Severity;
  evidence: Evidence | null;
  confidence: 'High' | 'Medium' | 'Low';
  fact_or_inference: 'Fact — directly quoted' | 'Inference';
  clarification_question?: string;
}

export interface CostBreakdown {
  vendor_id: string;
  monthly_base: number;
  gst_18: number;
  monthly_total: number;
  included: string[];
  excluded: string[];
  optional: string[];
  unknown_cost: string[];
}

export interface CriterionScore {
  criterion: string;
  weight: number;
  vendor_scores: Record<string, { score: number; points: number }>;
}

export interface Recommendation {
  state: 'recommend' | 'insufficient';
  callout_title: string;
  callout_body: string;
  mandatory_failures: Array<{
    vendor_name: string;
    requirement_code: string;
    requirement_text: string;
    status: FindingStatus;
  }>;
  strengths_weaknesses: Record<
    string,
    {
      strengths: string[];
      weaknesses: string[];
      unresolved: string[];
    }
  >;
}

export function formatINR(amount: number): string {
  const formatted = new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 0,
  }).format(amount);
  return `₹${formatted}`;
}

export function mapJobStatusToLifecycle(
  jobStatus: JobStatus | null | undefined,
  fallback: LifecycleStatusType
): LifecycleStatusType {
  if (!jobStatus) return fallback;
  if (jobStatus === 'queued' || jobStatus === 'extracting' || jobStatus === 'analysing') {
    return 'Processing';
  }
  if (jobStatus === 'failed') {
    return 'Error';
  }
  return fallback;
}

// 1. Evaluations Dataset
export const mockEvaluations: Evaluation[] = [
  {
    id: 'eval-1',
    name: 'Housekeeping Services — Andheri East Office, FY 2026–27',
    name_short: 'Housekeeping — Andheri East',
    category: 'Facilities / Housekeeping',
    contract_type: 'Monthly contract',
    total_requirements: 18,
    mandatory_requirements: 6,
    vendors_count: 3,
    updated_at: '12 Oct 2026',
    lifecycle_status: 'Analysed',
    latest_job: {
      id: 'job-1',
      status: 'done',
      started_at: '2026-10-12T10:00:00Z',
      finished_at: '2026-10-12T10:04:30Z',
      error_message: null,
      progress_step_label: 'Complete',
    },
  },
  {
    id: 'eval-2',
    name: 'Security Services — Powai Campus',
    name_short: 'Security — Powai Campus',
    category: 'Facilities / Security',
    contract_type: 'Monthly contract',
    total_requirements: 14,
    mandatory_requirements: 5,
    vendors_count: 2,
    updated_at: '10 Oct 2026',
    lifecycle_status: 'Requirements review',
    latest_job: {
      id: 'job-2',
      status: 'analysing',
      started_at: '2026-10-12T11:15:00Z',
      finished_at: null,
      error_message: null,
      progress_step_label: 'Reading proposal — page 9 of 16',
    },
  },
  {
    id: 'eval-3',
    name: 'Pantry & Cafeteria — BKC Office',
    name_short: 'Pantry & Cafeteria — BKC',
    category: 'Facilities / Housekeeping',
    contract_type: 'Monthly contract',
    total_requirements: 12,
    mandatory_requirements: 4,
    vendors_count: 3,
    updated_at: '08 Oct 2026',
    lifecycle_status: 'Stale',
    latest_job: {
      id: 'job-3',
      status: 'failed',
      started_at: '2026-10-08T09:20:00Z',
      finished_at: '2026-10-08T09:21:15Z',
      error_message: 'PDF extraction failed: Corrupted document header on cafeteria_rates.pdf',
      progress_step_label: 'Failed during extraction',
    },
  },
  {
    id: 'eval-4',
    name: 'Pest Control AMC — Thane Warehouse',
    name_short: 'Pest Control AMC — Thane Warehouse',
    category: 'Facilities / Housekeeping',
    contract_type: 'Annual contract',
    total_requirements: 8,
    mandatory_requirements: 3,
    vendors_count: 2,
    updated_at: '05 Oct 2026',
    lifecycle_status: 'Draft',
    latest_job: null,
  },
];

// 2. Vendors for eval-1
export const mockVendors: Vendor[] = [
  {
    id: 'vendor-brightnest',
    name: 'BrightNest Facility Services',
    tag: 'Lowest quote',
    score: 64,
    mandatory_failures: 1,
    monthly_base_inr: 385000,
    gst_rate: 0.18,
    monthly_gst_inr: 69300,
    monthly_total_inr: 454300,
    unknown_costs_count: 2,
    needs_review_count: 0,
  },
  {
    id: 'vendor-shubh',
    name: 'Shubh Housekeeping Pvt Ltd',
    tag: 'Strongest coverage',
    score: 86,
    mandatory_failures: 0,
    monthly_base_inr: 460000,
    gst_rate: 0.18,
    monthly_gst_inr: 82800,
    monthly_total_inr: 542800,
    unknown_costs_count: 0,
    needs_review_count: 0,
  },
  {
    id: 'vendor-urbankleen',
    name: 'UrbanKleen Services',
    score: 58,
    mandatory_failures: 0,
    monthly_base_inr: 410000,
    gst_rate: 0.18,
    monthly_gst_inr: 73800,
    monthly_total_inr: 483800,
    unknown_costs_count: 1,
    needs_review_count: 1,
  },
];

// 3. Requirements (8 detailed sample requirements from spec)
export const mockRequirements: Requirement[] = [
  {
    id: 'req-01',
    code: 'REQ-01',
    text: 'Minimum 12 housekeeping staff on site, Mon–Sat, 8 am–8 pm',
    category: 'Staffing',
    mandatory: true,
    acceptance_condition: '≥12 staff per shift',
    source: 'RFP p.3 §2.1',
  },
  {
    id: 'req-02',
    code: 'REQ-02',
    text: 'Washroom cleaning every 2 hours with checklist',
    category: 'Service',
    mandatory: true,
    acceptance_condition: 'Every ≤2 h, checklist provided',
    source: 'RFP p.3 §2.3',
  },
  {
    id: 'req-03',
    code: 'REQ-03',
    text: 'Washroom consumables included in monthly fee',
    category: 'Commercial',
    mandatory: true,
    acceptance_condition: 'Priced within base fee',
    source: 'RFP p.5 §4.1',
  },
  {
    id: 'req-04',
    code: 'REQ-04',
    text: 'Quarterly deep cleaning of carpets and upholstery',
    category: 'Service',
    mandatory: false,
    acceptance_condition: '4 per year',
    source: 'RFP p.4 §2.6',
  },
  {
    id: 'req-05',
    code: 'REQ-05',
    text: 'On-site supervisor during all shifts',
    category: 'Staffing',
    mandatory: true,
    acceptance_condition: 'Supervisor per shift',
    source: 'RFP p.3 §2.2',
  },
  {
    id: 'req-06',
    code: 'REQ-06',
    text: 'Ad-hoc cleaning response within 2 hours',
    category: 'SLA',
    mandatory: false,
    acceptance_condition: 'Response ≤2 h stated',
    source: 'RFP p.4 §3.1',
  },
  {
    id: 'req-07',
    code: 'REQ-07',
    text: 'Monthly pest control',
    category: 'Service',
    mandatory: false,
    acceptance_condition: '12 treatments per year',
    source: 'RFP p.4 §2.8',
  },
  {
    id: 'req-08',
    code: 'REQ-08',
    text: 'Police verification and PF/ESIC compliance',
    category: 'Compliance',
    mandatory: true,
    acceptance_condition: 'Certificates provided',
    source: 'RFP p.6 §5.2',
  },
];

// 4. 8x3 Findings Matrix
export const mockFindings: Finding[] = [
  // REQ-01
  {
    requirement_id: 'req-01',
    vendor_id: 'vendor-brightnest',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'BrightNest commits to deploying 12 trained housekeeping operatives across the operational window 8:00 AM to 8:00 PM, Monday through Saturday.',
      document: 'BrightNest_Proposal.pdf',
      page: 2,
      section: '§2.1 Staffing Schedule',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-01',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'A dedicated team of 14 housekeeping personnel (12 primary + 2 relievers) will be stationed on-site from 08:00 to 20:00, Mon–Sat.',
      document: 'Shubh_Proposal.docx',
      page: 3,
      section: '§1.2 Manpower Deployment',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-01',
    vendor_id: 'vendor-urbankleen',
    status: 'Not evidenced',
    needs_review: true,
    inferred: true,
    risk_types: ['Ambiguity', 'Contradiction'],
    severity: 'Medium',
    evidence: {
      quote: 'UrbanKleen will provide adequate manpower as required to maintain premier cleanliness. Shift sizes fluctuate based on client footfall.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 3,
      section: '§2.0 Manpower Scope',
    },
    confidence: 'Low',
    fact_or_inference: 'Inference',
    clarification_question: 'Please confirm the exact number of staff deployed per shift.',
  },

  // REQ-02
  {
    requirement_id: 'req-02',
    vendor_id: 'vendor-brightnest',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Washroom sanitation will occur on a strict 2-hour cadence with QR-verified digital checklists.',
      document: 'BrightNest_Proposal.pdf',
      page: 3,
      section: '§2.4 Restroom SLA',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-02',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Restroom checks and sanitisation are scheduled every 90 to 120 minutes with physical sign-off cards.',
      document: 'Shubh_Proposal.docx',
      page: 4,
      section: '§2.1 Washroom Protocols',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-02',
    vendor_id: 'vendor-urbankleen',
    status: 'Partially compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Restroom maintenance conducted three times daily: morning, midday, and evening.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 4,
      section: '§2.3 Restroom Schedule',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },

  // REQ-03 (Featured in Drawer L4/S6)
  {
    requirement_id: 'req-03',
    vendor_id: 'vendor-brightnest',
    status: 'Non-compliant',
    needs_review: false,
    inferred: false,
    risk_types: ['Exclusion', 'Unknown cost'],
    severity: 'High',
    evidence: {
      quote: 'Washroom consumables (tissue, hand wash, air freshener) are not included and will be billed at actuals.',
      highlight: 'not included',
      document: 'BrightNest_Proposal.pdf',
      page: 4,
      section: '§3.2 Exclusions',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
    clarification_question: 'Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals.',
  },
  {
    requirement_id: 'req-03',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'All standard washroom consumables (Kimberly-Clark or equivalent soap, rolls, sanitisers) are fully inclusive in the monthly billing.',
      document: 'Shubh_Proposal.docx',
      page: 5,
      section: '§3.1 Consumables Guarantee',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-03',
    vendor_id: 'vendor-urbankleen',
    status: 'Not evidenced',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: null,
    confidence: 'Low',
    fact_or_inference: 'Inference',
    clarification_question: 'Please clarify whether washroom consumables are included in the base fee or billed separately.',
  },

  // REQ-04
  {
    requirement_id: 'req-04',
    vendor_id: 'vendor-brightnest',
    status: 'Non-compliant',
    needs_review: false,
    inferred: false,
    risk_types: ['Exclusion'],
    severity: 'Medium',
    evidence: {
      quote: 'Carpet extraction and upholstery shampooing are excluded from routine scope and available on billable work orders.',
      document: 'BrightNest_Proposal.pdf',
      page: 4,
      section: '§3.2 Exclusions',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-04',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Quarterly deep extraction cleaning of all carpeted workspaces and fabric chairs included at no additional charge.',
      document: 'Shubh_Proposal.docx',
      page: 6,
      section: '§2.8 Periodic Deep Cleans',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-04',
    vendor_id: 'vendor-urbankleen',
    status: 'Partially compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Deep carpet shampooing is optional at ₹18,000 per quarter.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 5,
      section: '§4.2 Optional Add-ons',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },

  // REQ-05
  {
    requirement_id: 'req-05',
    vendor_id: 'vendor-brightnest',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'One dedicated full-time site supervisor will oversee housekeeping operations throughout each active shift.',
      document: 'BrightNest_Proposal.pdf',
      page: 2,
      section: '§2.2 Supervisory Structure',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-05',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: '24×7 on-site supervisory presence ensures compliance with client quality matrices.',
      document: 'Shubh_Proposal.docx',
      page: 3,
      section: '§1.3 Supervision',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-05',
    vendor_id: 'vendor-urbankleen',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'A shift supervisor is assigned to the facility during all working hours.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 2,
      section: '§1.4 Management',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },

  // REQ-06
  {
    requirement_id: 'req-06',
    vendor_id: 'vendor-brightnest',
    status: 'Not evidenced',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: null,
    confidence: 'Low',
    fact_or_inference: 'Inference',
    clarification_question: 'Please confirm SLA response time for emergency/ad-hoc cleaning spills.',
  },
  {
    requirement_id: 'req-06',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Immediate incident and spill response guaranteed within 45 to 90 minutes of dispatch call.',
      document: 'Shubh_Proposal.docx',
      page: 5,
      section: '§3.4 Incident Response SLA',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-06',
    vendor_id: 'vendor-urbankleen',
    status: 'Not evidenced',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: null,
    confidence: 'Low',
    fact_or_inference: 'Inference',
    clarification_question: 'Please confirm SLA response time for ad-hoc requests.',
  },

  // REQ-07
  {
    requirement_id: 'req-07',
    vendor_id: 'vendor-brightnest',
    status: 'Partially compliant',
    needs_review: false,
    inferred: false,
    risk_types: ['Unknown cost'],
    severity: 'Medium',
    evidence: {
      quote: 'Pest control services available on request through our licensed pest management affiliate; rate card provided upon survey.',
      document: 'BrightNest_Proposal.pdf',
      page: 5,
      section: '§3.5 Allied Services',
    },
    confidence: 'Medium',
    fact_or_inference: 'Fact — directly quoted',
    clarification_question: 'Please quote a fixed monthly price for pest control.',
  },
  {
    requirement_id: 'req-07',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Monthly herbal pest management and gel baiting included in base proposal pricing.',
      document: 'Shubh_Proposal.docx',
      page: 6,
      section: '§2.9 Pest Control Program',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-07',
    vendor_id: 'vendor-urbankleen',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Monthly general disinfection and pest mitigation treatments included in the contract.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 4,
      section: '§2.5 Pest Control',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },

  // REQ-08
  {
    requirement_id: 'req-08',
    vendor_id: 'vendor-brightnest',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: '100% police verification records and statutory PF/ESIC compliance challans submitted monthly.',
      document: 'BrightNest_Proposal.pdf',
      page: 6,
      section: '§5.1 Statutory Compliance',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-08',
    vendor_id: 'vendor-shubh',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'Full compliance with central and state labour acts; background verification dossier provided per staff member.',
      document: 'Shubh_Proposal.docx',
      page: 7,
      section: '§5.2 Compliance Certifications',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
  {
    requirement_id: 'req-08',
    vendor_id: 'vendor-urbankleen',
    status: 'Compliant',
    needs_review: false,
    inferred: false,
    risk_types: [],
    evidence: {
      quote: 'All deployed personnel are police-verified with active PF and ESIC registrations.',
      document: 'UrbanKleen_Proposal.pdf',
      page: 6,
      section: '§5.1 Statutory Obligations',
    },
    confidence: 'High',
    fact_or_inference: 'Fact — directly quoted',
  },
];

// 5. Cost Comparison Table
export const mockCostBreakdowns: CostBreakdown[] = [
  {
    vendor_id: 'vendor-brightnest',
    monthly_base: 385000,
    gst_18: 69300,
    monthly_total: 454300,
    included: ['Staffing', 'supervisor'],
    excluded: ['Consumables', 'deep cleaning'],
    optional: [],
    unknown_cost: ['Pest control "on request"', 'consumables at actuals'],
  },
  {
    vendor_id: 'vendor-shubh',
    monthly_base: 460000,
    gst_18: 82800,
    monthly_total: 542800,
    included: ['Staffing', '24×7 supervisor', 'consumables', 'deep cleaning', 'pest control'],
    excluded: [],
    optional: [],
    unknown_cost: [],
  },
  {
    vendor_id: 'vendor-urbankleen',
    monthly_base: 410000,
    gst_18: 73800,
    monthly_total: 483800,
    included: ['Staffing', 'pest control'],
    excluded: [],
    optional: ['Deep cleaning ₹18,000/quarter'],
    unknown_cost: ['Weekend coverage'],
  },
];

// 6. Scoring Breakdown (Points verified: 64, 86, 58)
export const mockCriterionScores: CriterionScore[] = [
  {
    criterion: 'Mandatory compliance',
    weight: 35,
    vendor_scores: {
      'vendor-brightnest': { score: 83, points: 29.1 },
      'vendor-shubh': { score: 100, points: 35.0 },
      'vendor-urbankleen': { score: 67, points: 23.4 },
    },
  },
  {
    criterion: 'Service coverage',
    weight: 20,
    vendor_scores: {
      'vendor-brightnest': { score: 65, points: 13.0 },
      'vendor-shubh': { score: 90, points: 18.0 },
      'vendor-urbankleen': { score: 70, points: 14.0 },
    },
  },
  {
    criterion: 'Cost comparability',
    weight: 20,
    vendor_scores: {
      'vendor-brightnest': { score: 55, points: 11.0 },
      'vendor-shubh': { score: 70, points: 14.0 },
      'vendor-urbankleen': { score: 60, points: 12.0 },
    },
  },
  {
    criterion: 'SLA / operational',
    weight: 15,
    vendor_scores: {
      'vendor-brightnest': { score: 50, points: 7.5 },
      'vendor-shubh': { score: 80, points: 12.0 },
      'vendor-urbankleen': { score: 20, points: 3.0 },
    },
  },
  {
    criterion: 'Unresolved risks',
    weight: 10,
    vendor_scores: {
      'vendor-brightnest': { score: 35, points: 3.5 },
      'vendor-shubh': { score: 70, points: 7.0 },
      'vendor-urbankleen': { score: 55, points: 5.5 },
    },
  },
];

// 7. Clarifications Per Vendor
export const mockClarificationQuestions: Record<string, string[]> = {
  'vendor-brightnest': [
    'Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals.',
    'Please quote a fixed monthly price for pest control.',
  ],
  'vendor-shubh': [],
  'vendor-urbankleen': [
    'Please confirm the exact number of staff deployed per shift.',
    'Please confirm whether Sunday and holiday coverage is included.',
  ],
};

// 8. Recommendation Summary
export const mockRecommendation: Recommendation = {
  state: 'recommend',
  callout_title: 'Recommended next step: proceed with Shubh Housekeeping Pvt Ltd, subject to clarifications.',
  callout_body:
    "Vendor B best meets requirements with no mandatory gaps. Vendor A is ₹75,000/month cheaper on base price but excludes consumables and deep cleaning, and its pest-control cost is unknown. Clarify Vendor A's consumables rate and Vendor C's staffing commitment before deciding.",
  mandatory_failures: [
    {
      vendor_name: 'BrightNest Facility Services',
      requirement_code: 'REQ-03',
      requirement_text: 'Washroom consumables included in monthly fee',
      status: 'Non-compliant',
    },
  ],
  strengths_weaknesses: {
    'vendor-brightnest': {
      strengths: ['Lowest base price ₹3,85,000', 'police verification provided'],
      weaknesses: ['Consumables excluded', 'deep cleaning excluded'],
      unresolved: ['Pest-control cost unknown', 'ad-hoc response time not stated'],
    },
    'vendor-shubh': {
      strengths: ['All 6 mandatory met', '24×7 supervisor', '2-hour response SLA'],
      weaknesses: ['Highest base price ₹4,60,000'],
      unresolved: ['None'],
    },
    'vendor-urbankleen': {
      strengths: ['Pest control included'],
      weaknesses: ['No SLA stated'],
      unresolved: ['Staffing "adequate manpower as required"', 'weekend coverage contradictory'],
    },
  },
};
