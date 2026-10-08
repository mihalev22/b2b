import createClient from 'openapi-fetch';
import type { paths } from './schema';

// Клиент API. Адреса, параметры и ответы проверяются по типам из schema.d.ts,
// а сам schema.d.ts генерируется командой `npm run gen:api` из openapi.yaml.
export const api = createClient<paths>({ baseUrl: window.location.origin });
