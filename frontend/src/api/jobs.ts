// Общий запрос задания: его используют экран хода обработки и экран результатов.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { Job } from './types';

const POLL_INTERVAL_MS = 1500;

export const JOB_NOT_FOUND = 'not-found';

// Точка, от которой считаем скорость: когда мы впервые увидели задание в работе
type Watch = { at: number; processed: number };

export type JobSnapshot = {
  job: Job;
  receivedAt: number;
  watch: Watch | null;
};

function jobKey(jobId: string) {
  return ['job', jobId] as const;
}

async function fetchJob(jobId: string, previous: JobSnapshot | undefined): Promise<JobSnapshot> {
  const { data, response } = await api.GET('/api/v1/jobs/{job_id}', {
    params: { path: { job_id: jobId } },
  });
  if (!data) {
    const missing = response.status === 404 || response.status === 422;
    throw new Error(missing ? JOB_NOT_FOUND : 'request-failed');
  }

  const now = Date.now();
  const watch =
    data.status === 'processing'
      ? (previous?.watch ?? { at: now, processed: data.processed_count })
      : null;
  return { job: data, receivedAt: now, watch };
}

export function isRunning(job: Job): boolean {
  return job.status === 'queued' || job.status === 'processing';
}

// Обработка закончилась, но ни одна позиция не обработана успешно
export function allFailed(job: Job): boolean {
  return job.status === 'done' && job.total_count > 0 && job.failed_count >= job.total_count;
}

// Сколько секунд осталось. Считаем по тому, сколько позиций обработано между опросами,
// и только по часам браузера — расхождение с часами сервера на оценку не влияет.
export function secondsLeft(snapshot: JobSnapshot): number | null {
  const { job, receivedAt, watch } = snapshot;
  if (!watch) return null;
  const processed = job.processed_count - watch.processed;
  const elapsed = (receivedAt - watch.at) / 1000;
  if (processed <= 0 || elapsed <= 0) return null;
  const perSecond = processed / elapsed;
  return Math.round((job.total_count - job.processed_count) / perSecond);
}

// poll: опрашивать сервер, пока задание в очереди или обрабатывается
export function useJob(jobId: string, options: { poll?: boolean } = {}) {
  const queryClient = useQueryClient();
  const poll = options.poll ?? false;

  return useQuery({
    queryKey: jobKey(jobId),
    queryFn: () => fetchJob(jobId, queryClient.getQueryData<JobSnapshot>(jobKey(jobId))),
    retry: (failures, failure) => failure.message !== JOB_NOT_FOUND && failures < 2,
    refetchInterval: (query) => {
      const current = query.state.data?.job;
      return poll && current && isRunning(current) ? POLL_INTERVAL_MS : false;
    },
  });
}
