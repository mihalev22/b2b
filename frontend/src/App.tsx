import { Route, Routes } from 'react-router-dom';
import AppLayout from './layout/AppLayout';
import UploadPage from './pages/UploadPage';
import JobProgressPage from './pages/JobProgressPage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';
import NotFoundPage from './pages/NotFoundPage';

// Адреса экранов:
//   /                        — загрузка файла
//   /jobs/:jobId             — ход обработки
//   /jobs/:jobId/results     — результаты
//   /history                 — история заданий
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<UploadPage />} />
        <Route path="/jobs/:jobId" element={<JobProgressPage />} />
        <Route path="/jobs/:jobId/results" element={<ResultsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
