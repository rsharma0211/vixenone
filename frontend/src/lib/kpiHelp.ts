export type KpiId =
  | 'evaluations_total'
  | 'needs_action'
  | 'analysed'
  | 'open_clarifications'
  | 'vendor_score'
  | 'mandatory_met'
  | 'monthly_cost';

export const KPI_HELP_TEXT: Record<KpiId, string> = {
  evaluations_total: 'All your evaluations, in any status.',
  needs_action:
    'Evaluations waiting on you: requirements to review, or results that need a re-run after a change.',
  analysed: 'Evaluations with up-to-date analysis results.',
  open_clarifications:
    'Unanswered questions to vendors, across all evaluations. Counts questions, not evaluations.',
  vendor_score:
    'Weighted total out of 100, calculated from the evidence. Adjust weights on Recommendation.',
  mandatory_met:
    'Mandatory requirements this vendor meets, backed by a quote from the proposal.',
  monthly_cost:
    'Monthly base price plus 18% GST, as stated. Unknown costs are listed below.',
};
