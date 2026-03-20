import { Navigate, useLocation } from 'react-router'

function SettingLegacyRedirect() {
  const location = useLocation()
  const nextPath = location.pathname.replace(/^\/setting\b/, '/settings')
  return <Navigate to={`${nextPath}${location.search}${location.hash}`} replace />
}

export default SettingLegacyRedirect
