import { useQuery } from '@tanstack/react-query';
import { Button, Card, Empty, Result, Table, Tag, Typography } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Job, JobStatus } from '../api/types';
import { texts } from '../texts';

const statusColor: Record<JobStatus, string> = {
  queued: 'default',
  processing: 'processing',
  done: 'success',
  failed: 'error',
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Готовое задание открывает результаты, остальные — экран хода обработки
function jobLink(job: Job): string {
  return job.status === 'done' ? `/jobs/${job.id}/results` : `/jobs/${job.id}`;
}

const columns: TableColumnsType<Job> = [
  {
    title: texts.history.columns.file,
    dataIndex: 'filename',
    render: (_, job) => <Link to={jobLink(job)}>{job.filename}</Link>,
  },
  {
    title: texts.history.columns.date,
    dataIndex: 'created_at',
    render: (_, job) => formatDate(job.created_at),
  },
  {
    title: texts.history.columns.count,
    dataIndex: 'total_count',
    align: 'right',
  },
  {
    title: texts.history.columns.status,
    dataIndex: 'status',
    render: (_, job) => <Tag color={statusColor[job.status]}>{texts.jobStatus[job.status]}</Tag>,
  },
];

export default function HistoryPage() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/v1/jobs', {
        params: { query: { limit: 50, offset: 0 } },
      });
      if (error || !data) throw new Error('Не удалось получить список заданий');
      return data;
    },
  });

  if (isError) {
    return (
      <Card>
        <Result
          status="warning"
          title={texts.history.error}
          subTitle={texts.history.errorHint}
          extra={
            <Button type="primary" onClick={() => refetch()}>
              {texts.history.retry}
            </Button>
          }
        />
      </Card>
    );
  }

  return (
    <Card>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        {texts.history.title}
      </Typography.Title>
      <Table<Job>
        rowKey="id"
        columns={columns}
        dataSource={data?.items}
        loading={isPending}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{
          emptyText: (
            <Empty description={texts.history.empty}>
              <Link to="/">
                <Button type="primary">{texts.history.emptyAction}</Button>
              </Link>
            </Empty>
          ),
        }}
      />
    </Card>
  );
}
