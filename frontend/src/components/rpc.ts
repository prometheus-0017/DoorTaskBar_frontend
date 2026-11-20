import { createMain } from '@xuri-rpc/websocket-sender'

export const hostId = 'frontend-' + Math.random()

// rpc 是模块级单例：App.vue 负责握手，groupView 等组件直接用它调 toTop
export let rpc: any = null

export async function prepareRpc() {
  const [client] = await createMain(hostId, window.location.hostname, 18765, '/')
  rpc = await client.getObject('rpc')
}
