import { useParams } from 'react-router'
import BotIndex from '../bot/index'
import ChatIndex from '../chat/index'
import DatasetIndex from '../dataset/index'
import ModelIndex from '../model/index'
import PluginIndex from '../plugin/index'
import SafeIndex from '../safe/index'
import StoreIndex from '../store/index'
import WorkflowIndex from '../workflow/index'

function BoxPage(props: { type: string; id: string }) {
  const { type = '', id = '' } = props
  const renderBox = () => {
    if (type.indexOf('chat') > -1) {
      return <ChatIndex></ChatIndex>
    }
    if (type.indexOf('bot') > -1) {
      return <BotIndex></BotIndex>
    }
    if (type.indexOf('dataset') > -1) {
      return <DatasetIndex></DatasetIndex>
    }
    if (type.indexOf('model') > -1) {
      return <ModelIndex></ModelIndex>
    }
    if (type.indexOf('plugin') > -1) {
      return <PluginIndex></PluginIndex>
    }
    if (type.indexOf('safe') > -1) {
      return <SafeIndex></SafeIndex>
    }
    if (type.indexOf('store') > -1) {
      return <StoreIndex></StoreIndex>
    }
    if (type.indexOf('workflow') > -1) {
      return <WorkflowIndex></WorkflowIndex>
    }
    return <ChatIndex></ChatIndex>
  }
  return renderBox()
}

export default BoxPage
