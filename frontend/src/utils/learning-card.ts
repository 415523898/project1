export type LearningCardStatus = 'unlearned' | 'studying' | 'learned'

/** Shared appearance; canvas geometry and each card's content stay with their view. */
export function learningCardStyle(
  status: LearningCardStatus,
  selected: boolean,
  linkedToReference = true,
) {
  return {
    borderRadius: '12px',
    borderWidth: '1px',
    borderLeftWidth: '4px',
    borderStyle: 'solid',
    background: 'linear-gradient(180deg, var(--dsw-alias-bg-layer-1) 0%, #fbfcff 100%)',
    borderColor: selected ? 'rgba(79, 124, 255, 0.85)' : 'rgba(20, 40, 80, 0.1)',
    borderLeftColor: !linkedToReference
      ? '#4f7cff'
      : status === 'learned'
        ? '#22a06b'
        : status === 'studying'
          ? '#f59e0b'
          : 'rgba(20, 40, 80, 0.18)',
    boxShadow: selected
      ? '0 0 0 3px rgba(79, 124, 255, 0.14), 0 18px 34px -26px rgba(20, 40, 80, 0.5)'
      : '0 10px 24px -22px rgba(20, 40, 80, 0.45)',
  }
}
