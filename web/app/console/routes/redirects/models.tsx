import { LegacyRedirect } from '../../shell/legacy-redirect'

export default function Redirect() {
  return <LegacyRedirect to={() => '/build/models'} />
}
