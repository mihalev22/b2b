import { Tooltip } from 'antd';
import { texts } from '../texts';

// Какие позиции показывать: все (null), подобранные автоматически или требующие проверки
export type StatusFilter = 'auto' | 'needs_review' | null;

type Props = {
  total: number;
  auto: number;
  needsReview: number;
  active: StatusFilter;
  onChange: (next: StatusFilter) => void;
};

type Tone = { text: string; background: string; border: string };

// Цвета совпадают с метками статусов в таблице
const tones: Record<'neutral' | 'good' | 'attention', Tone> = {
  neutral: { text: '#262626', background: '#fafafa', border: '#d9d9d9' },
  good: { text: '#237804', background: '#f6ffed', border: '#73d13d' },
  attention: { text: '#ad6800', background: '#fffbe6', border: '#ffc53d' },
};

type TileProps = {
  count: number;
  label: string;
  hint: string;
  tone: Tone;
  pressed: boolean;
  onClick: () => void;
};

function Tile({ count, label, hint, tone, pressed, onClick }: TileProps) {
  return (
    <Tooltip title={hint}>
      <button
        type="button"
        aria-pressed={pressed}
        onClick={onClick}
        style={{
          minWidth: 132,
          padding: '8px 14px',
          textAlign: 'left',
          font: 'inherit',
          color: tone.text,
          background: tone.background,
          border: `2px solid ${pressed ? tone.text : tone.border}`,
          borderRadius: 8,
          cursor: 'pointer',
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 600, lineHeight: 1.2 }}>{count}</div>
        <div style={{ fontSize: 13 }}>{label}</div>
      </button>
    </Tooltip>
  );
}

// Счётчики позиций, которые одновременно работают как фильтр таблицы
export default function StatusTiles({ total, auto, needsReview, active, onChange }: Props) {
  return (
    <div
      role="group"
      aria-label={texts.results.filters.label}
      style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}
    >
      <Tile
        count={total}
        label={texts.results.filters.all}
        hint={texts.results.filters.allHint}
        tone={tones.neutral}
        pressed={active === null}
        onClick={() => onChange(null)}
      />
      <Tile
        count={auto}
        label={texts.itemStatus.auto}
        hint={texts.results.filters.autoHint}
        tone={tones.good}
        pressed={active === 'auto'}
        onClick={() => onChange(active === 'auto' ? null : 'auto')}
      />
      <Tile
        count={needsReview}
        label={texts.itemStatus.needs_review}
        hint={texts.results.filters.reviewHint}
        tone={tones.attention}
        pressed={active === 'needs_review'}
        onClick={() => onChange(active === 'needs_review' ? null : 'needs_review')}
      />
    </div>
  );
}
