import { LegacyRedirect } from '../../shell/legacy-redirect'

export default function Redirect() {
  return <LegacyRedirect to={(_params, location) => location.pathname.replace(/^\/v2/, '') || '/'} />
}
