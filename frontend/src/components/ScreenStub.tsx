import { Card, Tag, Typography } from 'antd';
import { texts } from '../texts';

type Props = {
  title: string;
  description: string;
  jobId?: string;
};

// Временная заглушка экрана. Исчезнет, когда сверстаем настоящие экраны.
export default function ScreenStub({ title, description, jobId }: Props) {
  return (
    <Card>
      <Tag color="gold">{texts.stub.badge}</Tag>
      <Typography.Title level={2} style={{ marginTop: 12 }}>
        {title}
      </Typography.Title>
      <Typography.Paragraph>{description}</Typography.Paragraph>
      {jobId && (
        <Typography.Text type="secondary">
          {texts.stub.job}: {jobId}
        </Typography.Text>
      )}
    </Card>
  );
}
