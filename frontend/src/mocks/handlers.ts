// Обработчики запросов для моков: повторяют адреса из openapi.yaml.
// Пока нет живого сервера, браузер получает ответы отсюда.
import { delay, http, HttpResponse } from 'msw';
import { findPosition, searchCatalog } from './catalog';
import { db } from './db';
import type { ItemsQuery } from './db';
import type { ItemCorrection } from '../api/types';

const API = '/api/v1';

function notFound(what: string) {
  return HttpResponse.json({ detail: `${what} not found` }, { status: 404 });
}

function numberParam(url: URL, name: string, fallback: number): number {
  const raw = url.searchParams.get(name);
  const value = raw === null ? NaN : Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

function optionalNumber(url: URL, name: string): number | null {
  const raw = url.searchParams.get(name);
  if (raw === null || raw === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export const handlers = [
  http.get(`${API}/health`, () =>
    HttpResponse.json({
      status: 'ok',
      version: '0.1.0-mock',
      components: [{ name: 'mock', ok: true, detail: 'Ответы приходят из моков' }],
    }),
  ),

  http.post(`${API}/jobs`, async ({ request }) => {
    await delay(600);
    const form = await request.formData();
    const file = form.get('file');
    if (!(file instanceof File)) {
      return HttpResponse.json(
        { detail: [{ loc: ['body', 'file'], msg: 'Field required', type: 'missing' }] },
        { status: 422 },
      );
    }
    return HttpResponse.json(db.createJob(file.name), { status: 202 });
  }),

  http.get(`${API}/jobs`, async ({ request }) => {
    await delay(300);
    const url = new URL(request.url);
    return HttpResponse.json(db.listJobs(numberParam(url, 'limit', 50), numberParam(url, 'offset', 0)));
  }),

  http.get(`${API}/jobs/:jobId`, async ({ params }) => {
    await delay(150);
    const job = db.getJob(String(params.jobId));
    return job ? HttpResponse.json(job) : notFound('Job');
  }),

  http.get(`${API}/jobs/:jobId/items`, async ({ params, request }) => {
    await delay(300);
    const url = new URL(request.url);
    const sortBy = url.searchParams.get('sort_by');
    const query: ItemsQuery = {
      limit: numberParam(url, 'limit', 50),
      offset: numberParam(url, 'offset', 0),
      status: url.searchParams.get('status'),
      minConfidence: optionalNumber(url, 'min_confidence'),
      maxConfidence: optionalNumber(url, 'max_confidence'),
      q: url.searchParams.get('q'),
      sortBy: sortBy === 'confidence' || sortBy === 'updated_at' ? sortBy : 'row_number',
      sortOrder: url.searchParams.get('sort_order') === 'desc' ? 'desc' : 'asc',
    };
    const page = db.listItems(String(params.jobId), query);
    return page ? HttpResponse.json(page) : notFound('Job');
  }),

  http.post(`${API}/jobs/:jobId/accept`, async ({ params, request }) => {
    await delay(400);
    const body = (await request.json()) as { min_confidence?: number };
    const accepted = db.acceptAbove(String(params.jobId), body.min_confidence ?? 0);
    return accepted === undefined ? notFound('Job') : HttpResponse.json({ accepted_count: accepted });
  }),

  // В моках и csv, и xlsx отдаются как csv — настоящий xlsx сделает сервер.
  http.get(`${API}/jobs/:jobId/export`, async ({ params }) => {
    await delay(400);
    const csv = db.exportCsv(String(params.jobId));
    if (csv === undefined) return notFound('Job');
    return new HttpResponse(csv, {
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="result.csv"',
      },
    });
  }),

  http.patch(`${API}/items/:itemId`, async ({ params, request }) => {
    await delay(300);
    const body = (await request.json()) as ItemCorrection;
    const item = db.correctItem(String(params.itemId), body.ktru_code, body.ktru_name ?? null);
    return item ? HttpResponse.json(item) : notFound('Item');
  }),

  http.post(`${API}/items/:itemId/accept`, async ({ params }) => {
    await delay(200);
    const item = db.acceptItem(String(params.itemId));
    return item ? HttpResponse.json(item) : notFound('Item');
  }),

  http.post(`${API}/items/:itemId/revert`, async ({ params }) => {
    await delay(200);
    const item = db.revertItem(String(params.itemId));
    return item ? HttpResponse.json(item) : notFound('Item');
  }),

  // Важно: /ktru/search стоит раньше /ktru/:code, иначе «search» примут за код.
  http.get(`${API}/ktru/search`, async ({ request }) => {
    await delay(250);
    const url = new URL(request.url);
    const limit = numberParam(url, 'limit', 10);
    const items = searchCatalog(url.searchParams.get('q') ?? '', limit);
    return HttpResponse.json({ items, total: items.length, limit });
  }),

  http.get(`${API}/ktru/:code`, async ({ params }) => {
    await delay(200);
    const position = findPosition(String(params.code));
    return position ? HttpResponse.json(position) : notFound('Position');
  }),
];
