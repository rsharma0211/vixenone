export type * from './schema';
import type { components } from './schema';

export type Schemas = components['schemas'];

// Criteria
export type EvaluationCriterionResponse = Schemas['EvaluationCriterionResponse'];
export type EvaluationCriterionUpdateItem = Schemas['EvaluationCriterionUpdateItem'];
export type CriterionKind = Schemas['CriterionKind'];

// Evaluations
export type EvaluationSummaryResponse = Schemas['EvaluationSummaryResponse'];
export type EvaluationsListResponse = Schemas['EvaluationsListResponse'];
export type EvaluationKPIs = Schemas['EvaluationKPIs'];
export type EvaluationDetailResponse = Schemas['EvaluationDetailResponse'];
export type EvaluationCreate = Schemas['EvaluationCreate'];
export type EvaluationUpdate = Schemas['EvaluationUpdate'];
export type EvaluationStatus = Schemas['EvaluationStatus'];

// Vendors & Documents
export type VendorResponse = Schemas['VendorResponse'];
export type DocumentResponse = Schemas['DocumentResponse'];
export type DocumentKind = Schemas['DocumentKind'];
export type DocumentStatus = Schemas['DocumentStatus'];

// Requirements
export type RequirementItem = Schemas['RequirementItem'];
export type RequirementOrigin = Schemas['RequirementOrigin'];
export type ExtractRequirementsRequest = Schemas['ExtractRequirementsRequest'];

// Jobs
export type AnalysisJobResponse = Schemas['AnalysisJobResponse'];
export type JobKind = Schemas['JobKind'];
export type JobStatus = Schemas['JobStatus'];

// Results
export type EvaluationResultsResponse = Schemas['EvaluationResultsResponse'];
export type VendorResultItem = Schemas['VendorResultItem'];
export type FindingResponse = Schemas['FindingResponse'];
export type FindingEvidence = Schemas['FindingEvidence'];
export type CostBreakdownResponse = Schemas['CostBreakdownResponse'];
export type CriterionScoreRow = Schemas['CriterionScoreRow'];
export type CriterionScoreCell = Schemas['CriterionScoreCell'];
export type VendorTotalResult = Schemas['VendorTotalResult'];

// Chat
export type ChatTurnRequest = Schemas['ChatTurnRequest'];
export type ChatTurnResponse = Schemas['ChatTurnResponse'];
export type ChatExpect = Schemas['ChatExpect'];
export type ChatChoiceOption = Schemas['ChatChoiceOption'];
export type ChatSummary = Schemas['ChatSummary'];
export type ChatVendorSummary = Schemas['ChatVendorSummary'];
export type ChatJobInfo = Schemas['ChatJobInfo'];
export type ChatAction =
  | 'review_first'
  | 'run_analysis'
  | 'create_evaluation'
  | 'change_details'
  | (string & {});
export type ChatCollectedDetails = Schemas['ChatCollectedDetails'];
export type ChatDocumentSlot = Schemas['ChatDocumentSlot'];
