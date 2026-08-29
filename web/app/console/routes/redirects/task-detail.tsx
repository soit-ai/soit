import { LegacyRedirect } from '../../shell/legacy-redirect'

export default function Redirect() {
  return <LegacyRedirect to={(params) => `/execute/tasks/${params.taskId ?? ''}`} />
}
