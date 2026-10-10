import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Button, Card, Result, Skeleton, Table, Tag, Typography } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Item, ItemStatus } from '../api/types';
import { confidenceZone } from '../confidence';
import type { ConfidenceZone } from '../confidence';
import { texts } from '../texts';

const PAGE_SIZE = 50;
// Уже этой ширины таблица не сжимается, а прокручивается по горизонтали
const TABLE_MIN_WIDTH = 1100;
const NOT_FOUND = 'not-found';

async function fetchJobInfo(jobId: string) {
  const { data, response } = await api.GET('/api/v1/jobs/{job_id}', {
    params: { path: { job_id: jobId } },
  });
  if (!data) {
    const missing = response.status === 404 || response.status === 422;
    throw new Error(missing ? NOT_FOUND : 'request-failed');
  }
  return data;
}

async function fetchItems(jobId: string, page: number) {
  const { data } = await api.GET('/api/v1/jobs/{job_id}/items', {
    params: {
      path: { job_id: jobId },
      query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE },
    },
  });
  if (!data) throw new Error('request-failed');
  return data;
}

// Зелёный — можно доверять, жёлтый — стоит взглянуть, красный — проверить обязательно
const zoneColor: Record<ConfidenceZone, string> = {
  high: 'success',
  medium: 'warning',
  low: 'error',
  none: 'default',
};

const statusColor: Record<ItemStatus, string> = {
  pending: 'default',
  auto: 'default',
  needs_review: 'warning',
  accepted: 'success',
  corrected: 'processing',
};

function textOrDash(value: string | null | undefined) {
  return value ? value : texts.results.noValue;
}

const columns: TableColumnsType<Item> = [
  {
    title: texts.results.columns.row,
    dataIndex: 'row_number',
    width: 76,
    align: 'right',
  },
  {
    title: texts.results.columns.rawName,
    dataIndex: 'raw_name',
  },
  {
    title: texts.results.columns.name,
    key: 'name',
    width: 140,
    render: (_, item) => textOrDash(item.attributes?.name),
  },
  {
    title: texts.results.columns.brand,
    key: 'brand',
    width: 110,
    render: (_, item) => textOrDash(item.attributes?.brand),
  },
  {
    title: texts.results.columns.model,
    key: 'model',
    width: 130,
    render: (_, item) => textOrDash(item.attributes?.model),
  },
  {
    title: texts.results.columns.ktru,
    key: 'ktru',
    width: 240,
    render: (_, item) =>
      item.ktru_code ? (
        <>
          <div style={{ whiteSpace: 'nowrap' }}>{item.ktru_code}</div>
          <Typography.Text type="secondary">{item.ktru_name}</Typography.Text>
        </>
      ) : (
        <Typography.Text type="secondary">{texts.results.noCode}</Typography.Text>
      ),
  },
  {
    title: texts.results.columns.confidence,
    dataIndex: 'confidence',
    width: 124,
    align: 'right',
    render: (_, item) => (
      <Tag color={zoneColor[confidenceZone(item.confidence)]} style={{ marginInlineEnd: 0 }}>
        {item.confidence === null
          ? texts.results.noValue
          : texts.results.percent(item.confidence)}
      </Tag>
    ),
  },
  {
    title: texts.results.columns.status,
    dataIndex: 'status',
    width: 150,
    render: (_, item) => (
      <Tag color={statusColor[item.status]}>{texts.itemStatus[item.status]}</Tag>
    ),
  },
];

export default function ResultsPage() {
  const { jobId = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  // Номер страницы храним в адресе: ссылку можно переслать, а «Назад» работает как ожидается
  const page = Math.max(1, Math.floor(Number(searchParams.get('page'))) || 1);

  const jobQuery = useQuery({
    queryKey: ['job-info', jobId],
    queryFn: () => fetchJobInfo(jobId),
    retry: (failures, failure) => failure.message !== NOT_FOUND && failures < 2,
  });

  const job = jobQuery.data;
  const isReady = job?.status === 'done';

  const itemsQuery = useQuery({
    queryKey: ['items', jobId, page],
    queryFn: () => fetchItems(jobId, page),
    enabled: isReady,
    placeholderData: keepPreviousData,
  });

  function changePage(nextPage: number) {
    setSearchParams(nextPage > 1 ? { page: String(nextPage) } : {});
    window.scrollTo({ top: 0 });
  }

  if (!job) {
    if (jobQuery.isPending) {
      return (
        <Card>
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      );
    }
    if (jobQuery.error?.message === NOT_FOUND) {
      return (
        <Card>
          <Result
            status="404"
            title={texts.results.notFoundTitle}
            subTitle={texts.results.notFoundHint}
            extra={
              <Link to="/history">
                <Button type="primary">{texts.results.openHistory}</Button>
              </Link>
            }
          />
        </Card>
      );
    }
    return (
      <Card>
        <Result
          status="warning"
          title={texts.results.errorTitle}
          subTitle={texts.results.errorHint}
          extra={
            <Button type="primary" onClick={() => jobQuery.refetch()}>
              {texts.results.retry}
            </Button>
          }
        />
      </Card>
    );
  }

  if (job.status === 'failed') {
    return (
      <Card>
        <Result
          status="error"
          title={texts.results.failedTitle}
          subTitle={job.error ?? texts.results.failedHint}
          extra={
            <Link to="/">
              <Button type="primary">{texts.results.uploadAnother}</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  if (job.status !== 'done') {
    return (
      <Card>
        <Result
          status="info"
          title={texts.results.stillRunningTitle}
          subTitle={texts.results.stillRunningHint}
          extra={
            <Link to={`/jobs/${job.id}`}>
              <Button type="primary">{texts.results.openProgress}</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <Card>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        {texts.results.title}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ wordBreak: 'break-word', marginBottom: 4 }}>
        {job.filename}
      </Typography.Paragraph>
      <Typography.Paragraph>
        {texts.results.summary(
          job.total_count,
          job.auto_count ?? 0,
          job.needs_review_count ?? 0,
        )}
      </Typography.Paragraph>

      {itemsQuery.isError && !itemsQuery.data ? (
        <Result
          status="warning"
          title={texts.results.errorTitle}
          subTitle={texts.results.errorHint}
          extra={
            <Button type="primary" onClick={() => itemsQuery.refetch()}>
              {texts.results.retry}
            </Button>
          }
        />
      ) : (
        <Table<Item>
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={itemsQuery.data?.items}
          loading={itemsQuery.isFetching}
          scroll={{ x: TABLE_MIN_WIDTH }}
          locale={{ emptyText: texts.results.empty }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: itemsQuery.data?.total ?? 0,
            showSizeChanger: false,
            showTotal: (total, [from, to]) => texts.results.range(from, to, total),
            onChange: changePage,
          }}
        />
      )}
    </Card>
  );
}
