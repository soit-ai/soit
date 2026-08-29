/**
 * Console icon set, traced 1:1 from the v13 prototype's inline SVGs
 * (docs/product prototypes, v13 index.html). Stroke-based, 24x24 viewBox,
 * currentColor — sized per usage site exactly like the prototype markup.
 */

interface IconProps extends React.SVGProps<SVGSVGElement> {
  size?: number
}

function makeIcon(paths: React.ReactNode, defaultSize: number) {
  return function ConsoleIcon({ size = defaultSize, ...props }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden
        {...props}
      >
        {paths}
      </svg>
    )
  }
}

export const IconOverview = makeIcon(
  <>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </>,
  17
)

export const IconChat = makeIcon(
  <path d="M21 12a8 8 0 0 1-8 8H4l2-3a8 8 0 1 1 15-5Z" />,
  17
)

export const IconBuild = makeIcon(
  <>
    <path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z" />
    <path d="M3 7l9 5 9-5M12 12v10" />
  </>,
  17
)

export const IconExecute = makeIcon(<path d="m5 3 14 9-14 9V3Z" />, 17)

export const IconObserve = makeIcon(
  <path d="M3 12h4l2.5-7 4 14L16 12h5" />,
  17
)

export const IconGovern = makeIcon(
  <>
    <path d="M12 2 4.5 5v6c0 5 3.2 8.6 7.5 10 4.3-1.4 7.5-5 7.5-10V5L12 2Z" />
    <path d="m9 11.5 2 2 4-4.5" />
  </>,
  17
)

export const IconSettings = makeIcon(
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.5-1-2 3.4 2 1.6a7 7 0 0 0 0 2.4l-2 1.6 2 3.4 2.5-1a7 7 0 0 0 2 1.2L10 21h4l.4-2.6a7 7 0 0 0 2-1.2l2.5 1 2-3.4-2-1.6c.06-.4.1-.8.1-1.2Z" />
  </>,
  17
)

export const IconFeedback = makeIcon(
  <>
    <path d="m22 2-7 20-4-9-9-4 20-7Z" />
    <path d="M22 2 11 13" />
  </>,
  15
)

export const IconDocs = makeIcon(
  <>
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4a2 2 0 0 0-2-2H6.5A2.5 2.5 0 0 0 4 4.5v15Z" />
    <path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" />
  </>,
  15
)

export const IconSun = makeIcon(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </>,
  15
)

export const IconMoon = makeIcon(
  <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />,
  15
)

export const IconBell = makeIcon(
  <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0" />,
  15
)

export const IconSearch = makeIcon(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </>,
  13
)

export const IconChevronRight = makeIcon(<path d="m10 6 6 6-6 6" />, 13)

/** The parametric two-slab mark; slab colours come from the brand tokens. */
export function IconLogo({ size = 24, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 96 96" width={size} height={size} aria-label="SOIT" {...props}>
      <path d="M36 16 L56 16 L43 59 L23 59 Z" fill="var(--brand-blue-600)" />
      <path d="M52 38 L72 38 L59 81 L39 81 Z" fill="var(--brand-teal-500)" />
    </svg>
  )
}
