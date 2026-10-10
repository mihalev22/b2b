import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, Progress, Result, Skeleton, Typography } from 'antd';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Job } from '../api/types';
import { texts } from '../texts';

const POLL_INTERVAL_MS = 1500;
const NOT_FOUND = 'not-found';

async function fetchJob(jobId: string) {
  const { data, response } = await api.GET('/api/v1/jobs/{job_id}', {
    params: { path: { job_id: jobId } },
  });
  if (!data) {
    const missing = response.status === 404 || response.status === 422;
    throw new Error(missing ? NOT_FOUND : 'request-failed');
  }
  // Время ответа запоминаем здесь, чтобы по нему оценивать, сколько осталось
  return { job: data, fetchedAt: Date.now() };
}

function isRunning(job: Job): boolean {
  return job.status === 'queued' || job.status === 'processing';
}

// Оценка оставшегося времени по средней скорости с начала обработки
function secondsLeft(job: Job, fetchedAt: number): number | null {
  if (!job.started_at || job.processed_count === 0) return null;
  const elapsed = (fetchedAt - Date.parse(job.started_at)) / 1000;
  if (elapsed <= 0) return null;
  const perItem = elapsed / job.processed_count;
  return Math.round(perItem * (job.total_count - job.processed_count));
}

function UploadAnotherButton({ primary = false }: { primary?: boolean }) {
  return (
    <Link to="/">
      <Button type={primary ? 'primary' : 'default'}>{texts.progress.uploadAnother}</Button>
    </Link>
  );
}

export default function JobProgressPage() {
  const { jobId = '' } = useParams();
  const navigate = useNavigate();
  const sawRunning = useRef(false);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
    retry: (failures, failure) => failure.message !== NOT_FOUND && failures < 2,
    // Опрашиваем сервер, пока задание в очереди или обрабатывается
    refetchInterval: (query) => {
      const current = query.state.data?.job;
      return current && isRunning(current) ? POLL_INTERVAL_MS : false;
    },
  });

  const job = data?.job;
  const status = job?.status;
  const hasItems = (job?.total_count ?? 0) > 0;

  // Если человек дождался конца обработки на этом экране — сразу показываем результаты
  useEffect(() => {
    if (status === 'queued' || status === 'processing') {
      sawRunning.current = true;
    } else if (status === 'done' && hasItems && sawRunning.current) {
      navigate(`/jobs/${jobId}/results`, { replace: true });
    }
  }, [status, hasItems, jobId, navigate]);

  if (!job || !data) {
    if (isPending) {
      return (
        <Card style={{ maxWidth: 720, margin: '0 auto' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </Card>
      );
    }
    if (error?.message === NOT_FOUND) {
      return (
        <Card style={{ maxWidth: 720, margin: '0 auto' }}>
          <Result
            status="404"
            title={texts.progress.notFoundTitle}
            subTitle={texts.progress.notFoundHint}
            extra={[
              <Link to="/history" key="history">
                <Button type="primary">{texts.progress.openHistory}</Button>
              </Link>,
              <UploadAnotherButton key="upload" />,
            ]}
          />
        </Card>
      );
    }
    return (
      <Card style={{ maxWidth: 720, margin: '0 auto' }}>
        <Result
          status="warning"
          title={texts.progress.errorTitle}
          subTitle={texts.progress.errorHint}
          extra={
            <Button type="primary" onClick={() => refetch()}>
              {texts.progress.retry}
            </Button>
          }
        />
      </Card>
    );
  }

  if (job.status === 'failed') {
    return (
      <Card style={{ maxWidth: 720, margin: '0 auto' }}>
        <Result
          status="error"
          title={texts.progress.failedTitle}
          subTitle={
            <>
              {job.error && <div>{job.error}</div>}
              <div>{texts.progress.failedHint}</div>
            </>
          }
          extra={<UploadAnotherButton primary />}
        />
      </Card>
    );
  }

  if (job.status === 'done' && !hasItems) {
    return (
      <Card style={{ maxWidth: 720, margin: '0 auto' }}>
        <Result
          status="warning"
          title={texts.progress.emptyTitle}
          subTitle={texts.progress.emptyHint}
          extra={<UploadAnotherButton primary />}
        />
      </Card>
    );
  }

  if (job.status === 'done') {
    return (
      <Card style={{ maxWidth: 720, margin: '0 auto' }}>
        <Result
          status="success"
          title={texts.progress.doneTitle}
          subTitle={texts.progress.doneSummary(
            job.total_count,
            job.auto_count ?? 0,
            job.needs_review_count ?? 0,
          )}
          extra={
            <Link to={`/jobs/${job.id}/results`}>
              <Button type="primary">{texts.progress.openResults}</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  const isQueued = job.status === 'queued';
  const percent =
    job.total_count > 0 ? Math.floor((job.processed_count / job.total_count) * 100) : 0;
  const left = secondsLeft(job, data.fetchedAt);

  return (
    <Card style={{ maxWidth: 720, margin: '0 auto' }}>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        {texts.progress.title}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ wordBreak: 'break-word' }}>
        {job.filename}
      </Typography.Paragraph>

      <Typography.Title level={4} style={{ marginBottom: 8 }}>
        {isQueued ? texts.progress.queued : texts.progress.processing}
      </Typography.Title>
      <Progress percent={percent} status="active" />

      <div aria-live="polite">
        <Typography.Paragraph style={{ margin: '8px 0 0' }}>
          {isQueued || job.total_count === 0
            ? texts.progress.queuedHint
            : texts.progress.counter(job.processed_count, job.total_count)}
        </Typography.Paragraph>
        {left !== null && (
          <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
            {texts.progress.timeLeft(left)}
          </Typography.Paragraph>
        )}
      </div>

      <Typography.Paragraph type="secondary" style={{ margin: '24px 0 0' }}>
        {texts.progress.stayHint}
      </Typography.Paragraph>
    </Card>
  );
}
