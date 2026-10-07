// Короткие имена для типов из контракта.
// Сами типы руками не пишем — они берутся из сгенерированного schema.d.ts.
import type { components } from './schema';

type Schemas = components['schemas'];

export type Job = Schemas['JobOut'];
export type JobStatus = Job['status'];
export type JobPage = Schemas['JobPage'];
export type JobCreated = Schemas['JobCreated'];

export type Item = Schemas['ItemOut'];
export type ItemStatus = Item['status'];
export type ItemPage = Schemas['ItemPage'];
export type ItemAttributes = Schemas['ItemAttributes'];
export type ItemCorrection = Schemas['ItemCorrection'];
export type Candidate = Schemas['CandidateOut'];
export type Characteristic = Schemas['Characteristic'];

export type KtruPosition = Schemas['KtruPositionOut'];
export type KtruSearchPage = Schemas['KtruSearchPage'];

export type BulkAcceptResult = Schemas['BulkAcceptResult'];
export type HealthResponse = Schemas['HealthResponse'];
