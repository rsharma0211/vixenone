import type { AnalysisJobResponse, EvaluationStatus } from '@/lib/types';

export function isJobActive(job: AnalysisJobResponse | null | undefined): boolean {
  return (
    job !== null &&
    job !== undefined &&
    (job.status === 'queued' || job.status === 'extracting' || job.status === 'analysing')
  );
}

/**
 * Where a list row / sidebar entry opens:
 * draft or active job → Documents; requirements_review or stale → Requirements; analysed → Comparison.
 */
export function getEvaluationEntryPath(ev: {
  id: string;
  status: EvaluationStatus;
  latest_job?: AnalysisJobResponse | null;
}): string {
  if (ev.status === 'draft' || isJobActive(ev.latest_job)) {
    return `/evaluations/${ev.id}/documents`;
  }
  if (ev.status === 'requirements_review' || ev.status === 'stale') {
    return `/evaluations/${ev.id}/requirements`;
  }
  return `/evaluations/${ev.id}/comparison`;
}
