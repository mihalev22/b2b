import { Button, Result } from 'antd';
import { Link } from 'react-router-dom';
import { texts } from '../texts';

export default function NotFoundPage() {
  return (
    <Result
      status="404"
      title={texts.notFound.title}
      subTitle={texts.notFound.description}
      extra={
        <Link to="/">
          <Button type="primary">{texts.notFound.action}</Button>
        </Link>
      }
    />
  );
}
