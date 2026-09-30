/*
 * What a screen shows while it reads: placeholder rows in place of its content,
 * and a status message in its header.
 */

// Varied title widths, so the placeholder reads as rows rather than a grid.
const TITLE_WIDTHS = ['46%', '32%', '58%', '38%', '51%', '27%']

/**
 * `rows` placeholder rows of `--row-h` height. They carry no data, and are
 * hidden from assistive technology: `LoadStatus` says what is happening.
 */
export function SkeletonRows({ rows }: { rows: number }) {
  return (
    <div className="skeleton-rows" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="skeleton skeleton-short" />
          <span
            className="skeleton"
            style={{ inlineSize: TITLE_WIDTHS[index % TITLE_WIDTHS.length] }}
          />
          <span className="skeleton skeleton-pill" />
        </div>
      ))}
    </div>
  )
}

/**
 * A status region, rendered in every state: the read's message while it runs,
 * empty otherwise. Screen readers reliably announce a change to a live region
 * that already exists, but often miss one inserted together with its text.
 */
export function LoadStatus({ message }: { message: string }) {
  return (
    <p role="status" className="load-status">
      {message}
    </p>
  )
}
