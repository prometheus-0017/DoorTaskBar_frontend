import { reactive, ref } from 'vue'
import type { editableGroup } from './group'

// 弹窗状态与 Promise 管线：弹窗组件仍由 App.vue 渲染，任意组件调用 prompt/confirm/editGroup 即可等待结果
export const showConfirmDialog = ref(false)
export const confirmDialogProps = reactive({ title: '' })
let confirmDialogResolve: ((value: boolean) => void) | null = null

export function confirm(message: string): Promise<boolean> {
  confirmDialogProps.title = message
  showConfirmDialog.value = true
  return new Promise((resolve) => {
    confirmDialogResolve = resolve
  })
}
export function onConfirmCancel() {
  confirmDialogResolve?.(false)
  confirmDialogResolve = null
  showConfirmDialog.value = false
}
export function onConfirmSubmit() {
  confirmDialogResolve?.(true)
  confirmDialogResolve = null
  showConfirmDialog.value = false
}

export const showTextInput = ref(false)
export const textInputProps = reactive({ title: '', defaultValue: '', placeholder: '' })
let textInputResolve: ((value: string | null) => void) | null = null

export function prompt(title: string, defaultValue = '', placeholder = '请输入'): Promise<string | null> {
  textInputProps.title = title
  textInputProps.defaultValue = defaultValue
  textInputProps.placeholder = placeholder
  showTextInput.value = true
  return new Promise((resolve) => {
    textInputResolve = resolve
  })
}
export function onTextInputCancel() {
  textInputResolve?.(null)
  textInputResolve = null
  showTextInput.value = false
}
export function onTextInputSubmit(value: string) {
  textInputResolve?.(value)
  textInputResolve = null
  showTextInput.value = false
}

export const showModal = ref(false)
export const editData = ref<editableGroup>({ name: '', captureConditions: [] })
let editGroupResolve: ((g: editableGroup) => void) | null = null
let editGroupReject: (() => void) | null = null

export function onGroupCancel() {
  editGroupReject?.()
  editGroupReject = null
}
export function onGroupSubmit(data: editableGroup) {
  editGroupResolve?.(data)
  editGroupResolve = null
}

export async function editGroup(oldData?: editableGroup): Promise<editableGroup | null> {
  editData.value = oldData ?? { name: '', captureConditions: [] }
  showModal.value = true
  const editGroupPromise: Promise<editableGroup> = new Promise((resolve, reject) => {
    editGroupResolve = resolve
    editGroupReject = reject
  })
  try {
    return await editGroupPromise
  } catch {
    return null
  } finally {
    showModal.value = false
  }
}
