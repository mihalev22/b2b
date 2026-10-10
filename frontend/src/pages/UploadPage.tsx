import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Alert, Card, Typography, Upload } from 'antd';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { texts } from '../texts';

// Ограничения совпадают с серверными: api принимает файлы до 10 МБ и до 1000 позиций
const MAX_UPLOAD_MB = 10;
const MAX_ITEMS = 1000;
const ALLOWED_EXTENSIONS = ['xlsx', 'csv', 'pdf'];

// Проверка до отправки: возвращает текст отказа или null, если файл подходит
function validateFile(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!file.name.includes('.') || !ALLOWED_EXTENSIONS.includes(extension)) {
    return texts.upload.errors.type;
  }
  if (file.size === 0) return texts.upload.errors.empty;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return texts.upload.errors.size(MAX_UPLOAD_MB);
  return null;
}

// Если сервер объяснил отказ понятным текстом — показываем его, иначе общий текст
function serverMessage(error: unknown, status: number): string {
  if (status === 413) return texts.upload.errors.size(MAX_UPLOAD_MB);
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === 'string' && detail.trim() ? detail : texts.upload.errors.rejected;
}

async function createJob(file: File) {
  const form = new FormData();
  form.append('file', file);

  let result;
  try {
    result = await api.POST('/api/v1/jobs', {
      // В контракте поле описано как строка, а на деле это файл — отправляем его формой
      body: { file: file as unknown as string },
      bodySerializer: () => form,
    });
  } catch {
    throw new Error(texts.upload.errors.network);
  }

  if (result.error || !result.data) {
    throw new Error(serverMessage(result.error, result.response.status));
  }
  return result.data;
}

function UploadIcon() {
  return (
    <svg
      width="48"
      height="48"
      viewBox="0 0 48 48"
      fill="none"
      stroke="#1677ff"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M24 32V10" />
      <path d="M15 19l9-9 9 9" />
      <path d="M8 30v6a4 4 0 0 0 4 4h24a4 4 0 0 0 4-4v-6" />
    </svg>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const [validationError, setValidationError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: createJob,
    onSuccess: (job) => navigate(`/jobs/${job.job_id}`),
  });

  function handleFile(file: File) {
    upload.reset();
    const problem = validateFile(file);
    setValidationError(problem);
    if (!problem) upload.mutate(file);
  }

  const errorText = validationError ?? upload.error?.message ?? null;
  const isSending = upload.isPending || upload.isSuccess;

  return (
    <Card style={{ maxWidth: 720, margin: '0 auto' }}>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        {texts.upload.title}
      </Typography.Title>
      <Typography.Paragraph>{texts.upload.lead}</Typography.Paragraph>

      {errorText && (
        <Alert
          type="error"
          showIcon
          message={texts.upload.errorTitle}
          description={errorText}
          style={{ marginBottom: 16 }}
        />
      )}

      <Upload.Dragger
        multiple={false}
        showUploadList={false}
        disabled={isSending}
        beforeUpload={(file) => {
          handleFile(file);
          return false; // отправляем сами, через клиент API
        }}
      >
        <div style={{ padding: '16px 8px' }}>
          <UploadIcon />
          <Typography.Title level={4} style={{ margin: '12px 0 8px' }}>
            {isSending ? texts.upload.sending : texts.upload.dropTitle}
          </Typography.Title>
          <Typography.Text type="secondary">
            {isSending
              ? texts.upload.sendingHint
              : texts.upload.dropHint(MAX_UPLOAD_MB, MAX_ITEMS)}
          </Typography.Text>
        </div>
      </Upload.Dragger>

      <Typography.Paragraph style={{ margin: '16px 0 0' }}>
        {texts.upload.sampleQuestion}{' '}
        <a href="/sample.csv" download="Образец спецификации.csv">
          {texts.upload.sampleLink}
        </a>
      </Typography.Paragraph>
    </Card>
  );
}
