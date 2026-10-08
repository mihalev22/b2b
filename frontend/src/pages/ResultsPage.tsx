import { useParams } from 'react-router-dom';
import ScreenStub from '../components/ScreenStub';
import { texts } from '../texts';

export default function ResultsPage() {
  const { jobId } = useParams();
  return <ScreenStub {...texts.screens.results} jobId={jobId} />;
}
