// «База данных» для моков: живёт в памяти браузера и ведёт себя как будущий сервер.
// Задания, созданные через загрузку файла, запоминаются в localStorage,
// чтобы не пропадать при обновлении страницы. Правки кодов при обновлении сбрасываются.
import type { Candidate, Item, ItemStatus, Job } from '../api/types';
import { catalog, findPosition } from './catalog';

// ---------- Псевдослучайные числа: одинаковые данные при каждом запуске ----------

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function createRandom(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(random: () => number, list: readonly T[]): T {
  return list[Math.floor(random() * list.length)];
}

function fakeUuid(random: () => number): string {
  const hex = (n: number) =>
    Array.from({ length: n }, () => Math.floor(random() * 16).toString(16)).join('');
  return `${hex(8)}-${hex(4)}-4${hex(3)}-a${hex(3)}-${hex(12)}`;
}

// ---------- Генерация позиций ----------

type Template = {
  catalogIndex: number;
  name: string;
  brands: string[];
  models: string[];
  extras: string[];
};

const templates: Template[] = [
  { catalogIndex: 0, name: 'Ноутбук', brands: ['Dell', 'Lenovo', 'HP', 'Aquarius'], models: ['Latitude 5540', 'ThinkPad E16', 'ProBook 450 G10', 'Cmp NS685'], extras: ['16 ГБ', '8 ГБ 256 SSD', '15.6" i5'] },
  { catalogIndex: 1, name: 'Системный блок', brands: ['Aquarius', 'iRU', 'Depo'], models: ['Pro P30', 'Office 310', 'Neos 290'], extras: ['i5/8ГБ/SSD256', 'Ryzen 5 16 ГБ'] },
  { catalogIndex: 2, name: 'Монитор', brands: ['Samsung', 'LG', 'AOC', 'Xiaomi'], models: ['S24R350', '24MP400', '24B2XH', 'Mi 27'], extras: ['23.8" IPS', '27" FHD'] },
  { catalogIndex: 3, name: 'Клавиатура', brands: ['Logitech', 'Oklick', 'Defender'], models: ['K120', '180M', 'Element HB-520'], extras: ['USB чёрная', 'проводная'] },
  { catalogIndex: 4, name: 'Мышь', brands: ['Logitech', 'Oklick', 'A4Tech'], models: ['M185', '145M', 'OP-720'], extras: ['беспроводная', 'USB оптическая'] },
  { catalogIndex: 5, name: 'Принтер лазерный', brands: ['Pantum', 'HP', 'Kyocera'], models: ['P2500W', 'LaserJet M111a', 'PA2001'], extras: ['A4 ч/б', 'A4 Wi-Fi'] },
  { catalogIndex: 6, name: 'МФУ', brands: ['Pantum', 'Kyocera', 'Canon'], models: ['M6500', 'M2040dn', 'i-SENSYS MF3010'], extras: ['лазерное A4', 'A4 дуплекс'] },
  { catalogIndex: 7, name: 'SSD накопитель', brands: ['Kingston', 'Samsung', 'Netac'], models: ['A400', '870 EVO', 'SA500'], extras: ['480 ГБ SATA', '1 ТБ 2.5"'] },
  { catalogIndex: 8, name: 'Коммутатор', brands: ['TP-Link', 'D-Link', 'Eltex'], models: ['TL-SG1024D', 'DGS-1024D', 'MES2324'], extras: ['24 порта', '24x1G'] },
  { catalogIndex: 9, name: 'Маршрутизатор', brands: ['Keenetic', 'MikroTik', 'TP-Link'], models: ['Giga KN-1011', 'hEX S', 'Archer AX55'], extras: ['Wi-Fi 6', '5 портов'] },
  { catalogIndex: 10, name: 'Бумага офисная', brands: ['SvetoCopy', 'Снегурочка', 'Ballet'], models: ['Classic', 'Universal', 'Premier'], extras: ['A4 80 г/м2 500 л', 'А4 500 листов'] },
  { catalogIndex: 11, name: 'Ручка шариковая', brands: ['Erich Krause', 'BIC', 'Brauberg'], models: ['R-301', 'Round Stic', 'X-333'], extras: ['синяя 0.7 мм', 'синяя'] },
  { catalogIndex: 12, name: 'Карандаш', brands: ['Koh-i-Noor', 'Brauberg'], models: ['1500', 'Classic'], extras: ['HB с ластиком', 'чернографитный HB'] },
  { catalogIndex: 13, name: 'Папка-скоросшиватель', brands: ['Brauberg', 'Attache'], models: ['Office', 'Economy'], extras: ['A4 пластик синяя', 'А4'] },
  { catalogIndex: 14, name: 'Кресло офисное', brands: ['Бюрократ', 'Chairman'], models: ['CH-695N', '696'], extras: ['ткань чёрное', 'сетка серое'] },
  { catalogIndex: 15, name: 'Стол письменный', brands: ['Skyland', 'Монолит'], models: ['Simple S-1200', 'СМ1.11'], extras: ['1200x600 дуб', '1400 мм'] },
  { catalogIndex: 16, name: 'Светильник LED', brands: ['Gauss', 'ЭРА', 'IEK'], models: ['Армстронг 36W', 'SPO-6', 'ДВО 6560'], extras: ['595x595 36 Вт', '40 Вт 4000К'] },
  { catalogIndex: 17, name: 'Картридж', brands: ['HP', 'Pantum', 'Cactus'], models: ['CF259A', 'PC-211EV', 'CS-TK1170'], extras: ['чёрный', 'чёрный 3000 стр'] },
  { catalogIndex: 18, name: 'ИБП', brands: ['Ippon', 'APC', 'Powercom'], models: ['Back Basic 650', 'BX650LI', 'RPT-600A'], extras: ['650 ВА', '600 ВА 360 Вт'] },
  { catalogIndex: 19, name: 'Проектор', brands: ['Epson', 'ViewSonic'], models: ['EB-X49', 'PA503X'], extras: ['3600 лм XGA', '3800 лм'] },
];

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

function generateItems(jobId: string, total: number): Item[] {
  const random = createRandom(hash(jobId));
  const items: Item[] = [];

  for (let i = 0; i < total; i++) {
    const template = pick(random, templates);
    const position = catalog[template.catalogIndex];
    const brand = pick(random, template.brands);
    const model = pick(random, template.models);
    const rawName = `${template.name} ${brand} ${model} ${pick(random, template.extras)}`;
    const quantity = 1 + Math.floor(random() * 50);

    // Распределение уверенности: ~63% высокая, ~25% средняя, ~10% низкая, ~2% без кода
    const roll = random();
    let confidence: number | null;
    if (roll < 0.02) confidence = null;
    else if (roll < 0.12) confidence = round1(30 + random() * 29.9);
    else if (roll < 0.37) confidence = round1(60 + random() * 24.9);
    else confidence = round1(85 + random() * 14.9);

    const candidates: Candidate[] = [];
    if (confidence !== null) {
      candidates.push({
        ktru_code: position.ktru_code,
        ktru_name: position.ktru_name,
        confidence,
      });
      let next = confidence;
      const others = catalog.filter((p) => p !== position);
      const count = 2 + Math.floor(random() * 3);
      for (let c = 0; c < count; c++) {
        const other = others.splice(Math.floor(random() * others.length), 1)[0];
        next = round1(next * (0.45 + random() * 0.4));
        candidates.push({ ktru_code: other.ktru_code, ktru_name: other.ktru_name, confidence: next });
      }
    }

    const status: ItemStatus = confidence !== null && confidence >= 85 ? 'auto' : 'needs_review';

    items.push({
      id: fakeUuid(random),
      job_id: jobId,
      row_number: i + 2,
      raw_name: rawName,
      raw_columns: {
        '№': String(i + 1),
        'Наименование товара': rawName,
        'Ед. изм.': template.catalogIndex === 10 ? 'пач' : 'шт',
        'Кол-во': String(quantity),
      },
      attributes: {
        name: template.name,
        brand,
        model,
        characteristics: position.characteristics ?? [],
      },
      ktru_code: confidence === null ? null : position.ktru_code,
      ktru_name: confidence === null ? null : position.ktru_name,
      confidence,
      method: confidence === null ? null : confidence >= 85 ? 'hybrid' : 'llm',
      status,
      candidates,
      updated_at: new Date(Date.parse('2026-10-05T09:00:00Z') + i * 1000).toISOString(),
    });
  }
  return items;
}

// ---------- Задания ----------

type JobRecord = {
  id: string;
  filename: string;
  createdAt: number;
  total: number;
  // static — готовое задание из примеров; live — «обрабатывается» после загрузки файла
  kind: 'static' | 'live';
  failedWith?: string;
};

const DAY = 24 * 60 * 60 * 1000;
const QUEUE_MS = 1500;
const PROCESS_MS = 12000;

const seedJobs: JobRecord[] = [
  { id: 'c82cc353-9233-4ba2-8270-4f0139f37774', filename: 'Спецификация_оргтехника.xlsx', createdAt: Date.now() - 2 * 60 * 60 * 1000, total: 1000, kind: 'static' },
  { id: '5b1f0c9e-7a34-4d21-9e55-0d8f1c2a7b10', filename: 'Канцтовары_4_квартал.csv', createdAt: Date.now() - DAY, total: 48, kind: 'static' },
  { id: '9d3e6f12-4c8b-4f7a-b2a1-6e5d4c3b2a19', filename: 'Скан_заявки.pdf', createdAt: Date.now() - 3 * DAY, total: 0, kind: 'static', failedWith: 'Не удалось распознать таблицу в файле' },
];

const STORAGE_KEY = 'ktru-mock-jobs';

function loadCreatedJobs(): JobRecord[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as JobRecord[]) : [];
  } catch {
    return [];
  }
}

function saveCreatedJobs(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs.filter((j) => j.kind === 'live')));
  } catch {
    // хранилище недоступно — моки продолжают работать в памяти
  }
}

const jobs: JobRecord[] = [...loadCreatedJobs(), ...seedJobs];
const itemsByJob = new Map<string, Item[]>();
const originals = new Map<string, Item>();

function allItems(job: JobRecord): Item[] {
  let items = itemsByJob.get(job.id);
  if (!items) {
    items = generateItems(job.id, job.total);
    itemsByJob.set(job.id, items);
  }
  return items;
}

function progress(job: JobRecord): { status: Job['status']; processed: number } {
  if (job.failedWith) {
    const failed = job.kind === 'static' || Date.now() - job.createdAt > QUEUE_MS + 1500;
    return { status: failed ? 'failed' : 'processing', processed: 0 };
  }
  if (job.kind === 'static') return { status: 'done', processed: job.total };

  const elapsed = Date.now() - job.createdAt;
  if (elapsed < QUEUE_MS) return { status: 'queued', processed: 0 };
  if (elapsed >= QUEUE_MS + PROCESS_MS) return { status: 'done', processed: job.total };
  const share = (elapsed - QUEUE_MS) / PROCESS_MS;
  return { status: 'processing', processed: Math.floor(job.total * share) };
}

function visibleItems(job: JobRecord): Item[] {
  return allItems(job).slice(0, progress(job).processed);
}

function toJob(job: JobRecord): Job {
  const { status, processed } = progress(job);
  const items = visibleItems(job);
  const count = (s: ItemStatus) => items.filter((item) => item.status === s).length;
  const started = status === 'queued' ? null : job.createdAt + QUEUE_MS;
  const finished =
    status === 'done' || status === 'failed' ? job.createdAt + QUEUE_MS + PROCESS_MS : null;

  return {
    id: job.id,
    filename: job.filename,
    status,
    total_count: job.total,
    processed_count: processed,
    failed_count: 0,
    auto_count: count('auto'),
    needs_review_count: count('needs_review'),
    corrected_count: count('corrected'),
    error: status === 'failed' ? (job.failedWith ?? null) : null,
    parse_seconds: status === 'queued' ? null : 0.4,
    created_at: new Date(job.createdAt).toISOString(),
    started_at: started === null ? null : new Date(started).toISOString(),
    finished_at: finished === null ? null : new Date(finished).toISOString(),
  };
}

function findJob(jobId: string): JobRecord | undefined {
  return jobs.find((j) => j.id === jobId);
}

function findItem(itemId: string): Item | undefined {
  for (const job of jobs) {
    const item = allItems(job).find((i) => i.id === itemId);
    if (item) return item;
  }
  return undefined;
}

function touch(item: Item): void {
  if (!originals.has(item.id)) originals.set(item.id, { ...item });
  item.updated_at = new Date().toISOString();
}

// ---------- То, чем пользуются обработчики запросов ----------

export type ItemsQuery = {
  limit: number;
  offset: number;
  status: string | null;
  minConfidence: number | null;
  maxConfidence: number | null;
  q: string | null;
  sortBy: 'row_number' | 'confidence' | 'updated_at';
  sortOrder: 'asc' | 'desc';
};

export const db = {
  listJobs(limit: number, offset: number) {
    const sorted = [...jobs].sort((a, b) => b.createdAt - a.createdAt);
    return {
      items: sorted.slice(offset, offset + limit).map(toJob),
      total: sorted.length,
      limit,
      offset,
    };
  },

  getJob(jobId: string): Job | undefined {
    const job = findJob(jobId);
    return job && toJob(job);
  },

  // Подсказка для проверки экранов: если в имени файла есть «ошибка» или «error» —
  // задание упадёт, если «пусто» или «empty» — в нём не окажется позиций.
  createJob(filename: string) {
    const id = crypto.randomUUID();
    const lower = filename.toLowerCase();
    const isEmpty = lower.includes('пуст') || lower.includes('empty');
    const isBroken = lower.includes('ошибк') || lower.includes('error');
    const total = isEmpty || isBroken ? 0 : 60 + Math.floor(createRandom(hash(id))() * 340);

    jobs.unshift({
      id,
      filename,
      createdAt: Date.now(),
      total,
      kind: 'live',
      failedWith: isBroken ? 'Не удалось прочитать файл: неизвестная структура таблицы' : undefined,
    });
    saveCreatedJobs();
    return { job_id: id, status: 'queued' as const, filename };
  },

  listItems(jobId: string, query: ItemsQuery) {
    const job = findJob(jobId);
    if (!job) return undefined;

    let items = visibleItems(job);
    if (query.status) items = items.filter((i) => i.status === query.status);
    if (query.minConfidence !== null) {
      const min = query.minConfidence;
      items = items.filter((i) => i.confidence !== null && i.confidence >= min);
    }
    if (query.maxConfidence !== null) {
      const max = query.maxConfidence;
      items = items.filter((i) => i.confidence === null || i.confidence <= max);
    }
    if (query.q) {
      const needle = query.q.trim().toLowerCase();
      items = items.filter((i) =>
        [i.raw_name, i.ktru_code ?? '', i.ktru_name ?? ''].some((text) =>
          text.toLowerCase().includes(needle),
        ),
      );
    }

    const direction = query.sortOrder === 'desc' ? -1 : 1;
    const value = (i: Item): number => {
      if (query.sortBy === 'confidence') return i.confidence ?? -1;
      if (query.sortBy === 'updated_at') return Date.parse(i.updated_at);
      return i.row_number;
    };
    const sorted = [...items].sort((a, b) => (value(a) - value(b)) * direction);

    return {
      items: sorted.slice(query.offset, query.offset + query.limit),
      total: sorted.length,
      limit: query.limit,
      offset: query.offset,
    };
  },

  correctItem(itemId: string, ktruCode: string, ktruName: string | null): Item | undefined {
    const item = findItem(itemId);
    if (!item) return undefined;
    touch(item);
    item.ktru_code = ktruCode;
    item.ktru_name = ktruName ?? findPosition(ktruCode)?.ktru_name ?? null;
    item.method = 'manual';
    item.status = 'corrected';
    return item;
  },

  acceptItem(itemId: string): Item | undefined {
    const item = findItem(itemId);
    if (!item) return undefined;
    touch(item);
    item.status = 'accepted';
    return item;
  },

  revertItem(itemId: string): Item | undefined {
    const item = findItem(itemId);
    if (!item) return undefined;
    const original = originals.get(itemId);
    if (original) {
      Object.assign(item, original);
      originals.delete(itemId);
    }
    return item;
  },

  acceptAbove(jobId: string, minConfidence: number): number | undefined {
    const job = findJob(jobId);
    if (!job) return undefined;
    let accepted = 0;
    for (const item of visibleItems(job)) {
      const waiting = item.status === 'auto' || item.status === 'needs_review';
      if (waiting && item.confidence !== null && item.confidence >= minConfidence) {
        touch(item);
        item.status = 'accepted';
        accepted++;
      }
    }
    return accepted;
  },

  exportCsv(jobId: string): string | undefined {
    const job = findJob(jobId);
    if (!job) return undefined;
    const cell = (text: string | number | null) => `"${String(text ?? '').replace(/"/g, '""')}"`;
    const header = ['Строка', 'Наименование', 'Код КТРУ', 'Наименование КТРУ', 'Уверенность, %', 'Статус'];
    const rows = visibleItems(job).map((i) =>
      [i.row_number, i.raw_name, i.ktru_code, i.ktru_name, i.confidence, i.status].map(cell).join(';'),
    );
    return '\uFEFF' + [header.map(cell).join(';'), ...rows].join('\r\n');
  },
};
