import { NavLink } from 'react-router'

import { IconBack } from './icons'

/** Prototype .backlink — the "Back to …" link above a detail header. */
export function Backlink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink to={to} className="backlink">
      <IconBack />
      {children}
    </NavLink>
  )
}
