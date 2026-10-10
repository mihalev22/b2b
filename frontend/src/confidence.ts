// Пороги цветовых зон уверенности, в процентах.
// Временные значения до калибровки — итоговые даст ИИ-инженер (срок 22 октября).
export const CONFIDENCE_HIGH = 85;
export const CONFIDENCE_MEDIUM = 60;

export type ConfidenceZone = 'high' | 'medium' | 'low' | 'none';

export function confidenceZone(value: number | null): ConfidenceZone {
  if (value === null) return 'none';
  if (value >= CONFIDENCE_HIGH) return 'high';
  if (value >= CONFIDENCE_MEDIUM) return 'medium';
  return 'low';
}
