import './shell.css'

import { Fragment, useId } from 'react'
import type { ReactNode } from 'react'

import { JobsIndicator } from '../jobs/JobsIndicator'
import { LIST_HREF } from '../route'
import type { Route } from '../route'
import { Icon } from '../ui/Icon'
import type { IconName } from '../ui/Icon'
import { ToastRegion } from '../ui/ToastRegion'
import { useThemeChoice } from './theme'
import type { ThemeChoice } from './theme'

/**
 * The frame around every page: a skip control, the sticky header — brand,
 * primary navigation, a status slot, the theme control — and the toast region.
 * The screens keep rendering their own <main>, one shown at a time.
 */

/**
 * Focus the shown page's level-one heading (every page `h1` has tabIndex -1).
 * A fragment link would change the hash, which the router reads as a route.
 */
export function focusPageHeading(options?: FocusOptions): void {
  document.querySelector<HTMLElement>('main:not([hidden]) h1')?.focus(options)
}

const THEME_OPTIONS: readonly { choice: ThemeChoice; label: string; icon: IconName }[] = [
  { choice: 'system', label: 'System', icon: 'monitor' },
  { choice: 'light', label: 'Light', icon: 'sun' },
  { choice: 'dark', label: 'Dark', icon: 'moon' },
]

/** System, Light or Dark, as native radios: arrow keys move the choice. */
function ThemeControl() {
  const [choice, choose] = useThemeChoice()
  const name = useId()
  return (
    <fieldset className="segmented theme-control">
      <legend className="visually-hidden">Color scheme</legend>
      {THEME_OPTIONS.map((option) => (
        <Fragment key={option.choice}>
          <input
            className="visually-hidden"
            type="radio"
            id={`${name}-${option.choice}`}
            name={name}
            checked={choice === option.choice}
            onChange={() => choose(option.choice)}
          />
          <label htmlFor={`${name}-${option.choice}`} title={option.label}>
            <Icon name={option.icon} />
            <span className="visually-hidden">{option.label}</span>
          </label>
        </Fragment>
      ))}
    </fieldset>
  )
}

/** The product mark: a film reel on an accent tile. */
function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
      <rect className="brand-tile" width="24" height="24" rx="6.5" />
      <circle className="brand-reel" cx="12" cy="12" r="7.25" />
      <circle className="brand-hole" cx="12" cy="8.25" r="1.6" />
      <circle className="brand-hole" cx="12" cy="15.75" r="1.6" />
      <circle className="brand-hole" cx="8.25" cy="12" r="1.6" />
      <circle className="brand-hole" cx="15.75" cy="12" r="1.6" />
      <circle className="brand-hole" cx="12" cy="12" r="0.9" />
    </svg>
  )
}

export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  return (
    <>
      <button
        type="button"
        className="btn btn-primary skip-link"
        onClick={() => focusPageHeading()}
      >
        Skip to content
      </button>
      <header className="app-header">
        <div className="app-header-inner">
          <span className="brand">
            <BrandMark />
            <span className="brand-name">auto-reel</span>
          </span>
          <nav className="app-nav" aria-label="Primary">
            <a href={LIST_HREF} aria-current={route.page === 'list' ? 'page' : undefined}>
              Events
            </a>
          </nav>
          <div className="shell-status">
            <JobsIndicator />
          </div>
          <ThemeControl />
        </div>
      </header>
      {children}
      <ToastRegion />
    </>
  )
}
