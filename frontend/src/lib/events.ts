export const EVALUATION_CHANGED_EVENT = 'vixen:evaluation-changed';

export interface EvaluationChangedDetail {
  evaluationId?: string | null;
}

export function notifyEvaluationChanged(evaluationId?: string | null): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent<EvaluationChangedDetail>(EVALUATION_CHANGED_EVENT, {
        detail: { evaluationId },
      })
    );
  }
}
