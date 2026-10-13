/**
 * Central map of scoring explanation help text per criterion.
 * Keyed by builtin key, plus 'custom' for user-created criteria.
 */
export const CRITERIA_SCORING_HELP: Record<string, string> = {
  mandatory_compliance:
    'Average over mandatory requirements: met 100, partly 50, failed or not shown 0.',
  service_coverage:
    'Judged from the proposal against the guidance: met 100, partly 50, not met 0.',
  cost_comparability:
    'Starts at 100. Minus 40 if no monthly base price, minus 15 per unknown cost.',
  sla_operational:
    'Judged from the proposal against the guidance: met 100, partly 50, not met 0.',
  unresolved_risks:
    'Starts at 100. Minus 20, 10 or 5 per high, medium or low risk.',
  custom:
    'Judged from the proposal against your guidance: met 100, partly 50, not met 0.',
};

export function getCriteriaScoringHelp(builtinKey?: string | null): string {
  if (builtinKey && builtinKey in CRITERIA_SCORING_HELP) {
    return CRITERIA_SCORING_HELP[builtinKey];
  }
  return CRITERIA_SCORING_HELP.custom;
}
