import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Моки включены при разработке (npm run dev).
// Чтобы ходить на настоящий сервер, создайте файл .env.local со строкой VITE_USE_MOCKS=false
async function enableMocks(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS === 'false') return;
  const { worker } = await import('./mocks/browser');
  await worker.start();
}

enableMocks().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ConfigProvider locale={ruRU}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ConfigProvider>
    </StrictMode>,
  );
});
