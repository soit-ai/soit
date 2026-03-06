import { useParams } from 'react-router'
import { useTranslation } from '@/i18n'
import BoxPage from './box'
function IndexPage() {
  // const { setTitle } = useSiteContext()
  const { t } = useTranslation()
  const { type = '', id = '' } = useParams()
  // useEffect(() => {
  //   const title = t('window.title', { title: t('c.store') })
  //   setTitle(title)
  // }, [setTitle, t])

  return <BoxPage type={type} id={id}></BoxPage>
}

export default IndexPage
