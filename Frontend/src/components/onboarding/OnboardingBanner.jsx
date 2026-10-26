
export default function OnboardingBanner({ onDismiss }) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--border-light)] bg-[var(--accent-bg)] px-4 py-2 text-xs text-[var(--text)]">
      <span>
        👋 This example pipeline filters student grades, averages them by subject, sorts the
        result, and charts it. Click any node to see how it's configured, or hit{' '}
        <strong>New</strong> to start your own.
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="ui-btn ui-btn-ghost shrink-0"
      >
        Dismiss ✕
      </button>
    </div>
  )
}
