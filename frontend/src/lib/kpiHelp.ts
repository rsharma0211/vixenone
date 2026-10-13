export type KpiId =
  | 'evaluations_total'
  | 'needs_action'
  | 'analysed'
  | 'open_clarifications';

export const KPI_HELP_TEXT: Record<KpiId, string> = {
  evaluations_total: 'All your evaluations, in any status.',
  needs_action:
    'Evaluations waiting on you: requirements to review, or results that need a re-run after a change.',
  analysed: 'Evaluations with up-to-date analysis results.',
  open_clarifications:
    'Unanswered questions to vendors, across all evaluations. Counts questions, not evaluations.',
};
