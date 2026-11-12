import { reactive, ref, type Ref } from 'vue'
import { getId } from '../nnode.js'
import type { Group, Task } from './group'
import { config } from './config'
import { prompt, confirm, editGroup } from './dialogs'
import { rpc } from './rpc'

export type fullId = string
export type taskId = number
export interface ItemProxy {
  item: Task | Group
  type: 'list' | 'tag'
}

export function mkFullId(id: taskId, sys: string): fullId {
  return `${sys}%${id}`
}
export function taskEqual(a: Task | null | undefined, b: Task | null | undefined) {
  if (a == null && b == null) {
    return true
  }
  if (a == null || b == null) {
    return false
  }
  return mkFullId(a.id, a.system) == mkFullId(b.id, b.system)
}

// ===== group 树的状态 ===== 
// 原先散在 App.vue 里的“当前分组/拖拽/悬停/搜索游标”统一收在这里，
// 每一层视图只按传入的 parent 取值，不再读全局的“当前 group”
export const groups = ref<Group[]>([])
// 顶层选中的 group id（顶层相当于 parent=null 的那个层级，选中项不持久化）
export const currentTaskListShowing = ref('main')
export const itemDragging: Ref<ItemProxy | null> = ref(null)
export const currentItemClicked: Ref<ItemProxy | null> = ref(null)
export const hoverState = reactive<Record<fullId, boolean>>({})
export const globalQueryCursor: Group = reactive(makeGroup('', null))

export function makeGroup(name: string, previous: string | null, tasks: Task[] = []): Group {
  return {
    id: getId(),
    name,
    tasks,
    searchQuery: '',
    scrollStatus: 0,
    captureConditions: [],
    previous
  }
}

export function findGroup(id: string | null | undefined): Group | undefined {
  if (id == null) {
    return undefined
  }
  return groups.value.find(g => g.id === id)
}
export function getListById(tagId: string): Task[] | null {
  return findGroup(tagId)?.tasks ?? null
}
export function parentOf(g: Group): Group | null {
  return g.previous ? findGroup(g.previous) ?? null : null
}
export function childrenOf(parent: Group | null): Group[] {
  // 扁平数组的顺序就是同级的顺序
  return groups.value.filter(g => g.previous === (parent ? parent.id : null))
}
export function hasChildren(g: Group | null): boolean {
  return g != null && childrenOf(g).length > 0
}

export function selectedChild(parent: Group | null): Group | null {
  const list = childrenOf(parent)
  if (list.length === 0) {
    return null
  }
  if (!parent) {
    return findGroup(currentTaskListShowing.value) ?? list[0]
  }
  const cur = findGroup(parent.subCurrent)
  if (cur && cur.previous === parent.id) {
    return cur
  }
  return list[0]
}
export function setSelectedChild(parent: Group | null, id: string) {
  if (parent) {
    parent.subCurrent = id
  } else {
    currentTaskListShowing.value = id
  }
}
export function currentGroup(): Group | null {
  return selectedChild(null)
}

// 需求 7：追加的目标是“最深选中链”末端的那个 group，也就是画面上最下面一层的 group
export function followSelection(g: Group): Group {
  let cur = g
  const seen = new Set<string>([g.id])
  while (true) {
    const next = selectedChild(cur)
    if (next == null || seen.has(next.id)) {
      return cur
    }
    seen.add(next.id)
    cur = next
  }
}

export function queryCursorFor(g: Group): Group {
  return config.globalQuery ? globalQueryCursor : g
}
export function visibleTasks(g: Group): Task[] {
  let query = queryCursorFor(g).searchQuery.toLowerCase()
  if (config.shouldTrim) {
    query = query.trim()
  }
  return g.tasks.filter(item =>
    (item.modifiedName || item.originalName).toLowerCase().includes(query) || (item.processName)?.toLocaleLowerCase().includes(query)
  )
}

// ===== 结构变换 ===== 

// candidate 是否处在 node 的子树里（candidate === node 也算），用于拖拽时的环路检测
export function isDescendantOf(candidate: Group | null, node: Group | null): boolean {
  if (candidate == null || node == null) {
    return false
  }
  let cur: Group | undefined = candidate
  const seen = new Set<string>()
  while (cur) {
    if (cur.id === node.id) {
      return true
    }
    if (seen.has(cur.id)) {
      return false
    }
    seen.add(cur.id)
    cur = findGroup(cur.previous)
  }
  return false
}

// 把 dragged 挪到 newParent 这一层，anchor 非空时插在该同级之前
function relocate(dragged: Group, newParent: Group | null, anchor: Group | null) {
  const from = groups.value.indexOf(dragged)
  if (from === -1) {
    return
  }
  const oldParent = parentOf(dragged)
  groups.value.splice(from, 1)
  dragged.previous = newParent ? newParent.id : null
  let to: number
  if (anchor) {
    const anchorIdx = groups.value.indexOf(anchor)
    to = anchorIdx === -1 ? groups.value.length : anchorIdx
  } else {
    const siblings = groups.value.filter(g => g.previous === (newParent ? newParent.id : null))
    to = siblings.length ? groups.value.indexOf(siblings[siblings.length - 1]) + 1 : groups.value.length
  }
  groups.value.splice(to, 0, dragged)
  if (oldParent && oldParent !== newParent && oldParent.subCurrent === dragged.id) {
    const rest = childrenOf(oldParent)
    oldParent.subCurrent = rest.length ? rest[0].id : null
  }
  if (newParent && newParent !== oldParent) {
    // 换了层级才顺带选中它，否则新位置看不到被拖的 group；同级重排不动选中项
    newParent.subCurrent = dragged.id
  }
}

// 需求 3：把 group 拖到某个 group 的条目上 ⇒ 成为那个 group 的下级
export function attachAsChild(dragged: Group, owner: Group) {
  if (dragged === owner || dragged.id === 'main' || isDescendantOf(owner, dragged)) {
    return
  }
  relocate(dragged, owner, null)
}

// 需求 6：拖到父标签（或别的层的标签）⇒ 并入目标标签所在的层，目标是顶层标签时 previous 变成 null
export function reparentToLevel(dragged: Group, target: Group) {
  if (dragged === target || dragged.id === 'main') {
    return
  }
  const newParent = parentOf(target)
  if (isDescendantOf(newParent, dragged)) {
    return
  }
  relocate(dragged, newParent, target)
}

export function dropOnTag(dragged: Group, target: Group) {
  if (dragged === target) {
    return
  }
  if (dragged.previous === target.previous) {
    // 需求 9：同级之间只是排序
    relocate(dragged, dragged.previous ? findGroup(dragged.previous) ?? null : null, target)
    return
  }
  reparentToLevel(dragged, target)
}

// 标签被 drop 时的统一入口：拖 group 走层级/排序，拖条目走“追加到最下层”
export function dropOnTagTarget(target: Group) {
  const dragging = itemDragging.value
  if (!dragging) {
    return
  }
  itemDragging.value = null
  if (dragging.type == 'tag') {
    dropOnTag(dragging.item as Group, target)
    return
  }
  appendTaskToGroup(dragging.item as Task, target)
}

// 需求 7 的“追加”入口：新窗口、拖到标签上都追加到最下层
export function appendTaskToGroup(task: Task, group: Group) {
  const target = followSelection(group)
  if (target.tasks.some(t => taskEqual(t, task))) {
    return
  }
  target.tasks.push(task)
}

// 复制当前组（Ctrl+D）：只复制组本身，下级仍属于原组（克隆子树会让两个组声称同一批下级）
export function duplicateGroup(src: Group) {
  const copy = makeGroup(src.name + '副本', src.previous)
  copy.tasks = [...src.tasks]
  copy.captureConditions = JSON.parse(JSON.stringify(src.captureConditions || []))
  copy.captureIndex = JSON.parse(JSON.stringify(src.captureIndex || {}))
  const idx = groups.value.indexOf(src)
  groups.value.splice(idx + 1, 0, copy)
  selectTag(parentOf(src), copy)
}

export function deleteGroupWithRehome(id: string) {
  const idx = groups.value.findIndex(g => g.id === id)
  if (idx === -1) {
    return
  }
  const gone = groups.value[idx]
  const siblings = childrenOf(parentOf(gone))
  const posInSiblings = siblings.findIndex(g => g.id === id)
  groups.value.splice(idx, 1)
  // 子级上挂到被删组的父级，否则会留下看不见的孤儿
  for (const child of groups.value.filter(g => g.previous === id)) {
    child.previous = gone.previous
  }
  const remaining = groups.value.filter(g => g.previous === gone.previous)
  const next = remaining[Math.max(0, Math.min(posInSiblings - 1, remaining.length - 1))]
  const parent = gone.previous ? findGroup(gone.previous) ?? null : null
  if (parent) {
    parent.subCurrent = next ? next.id : null
  } else {
    currentTaskListShowing.value = next ? next.id : 'main'
  }
}

// 旧 status.json 没有 previous/视图字段，坏数据（自指、指向不存在的 id、成环）在这里自愈
export function normalizeGroups() {
  const byId = new Map(groups.value.map(g => [g.id, g]))
  for (const g of groups.value) {
    if (typeof g.previous !== 'string' || g.previous === g.id || !byId.has(g.previous)) {
      g.previous = null
    }
    if (typeof g.subRatio !== 'number' || !(g.subRatio > 0 && g.subRatio < 1)) {
      g.subRatio = 0.5
    }
    if (typeof g.searchVisible !== 'boolean') {
      g.searchVisible = true
    }
    g.subCurrent ??= null
    g.tasks ??= []
    g.captureConditions ??= []
    g.scrollStatus ??= 0
    g.searchQuery ??= ''
  }
  // 沿 previous 上溯做三色 DFS，谁把环闭上就断开谁的边
  const state = new Map<string, 1 | 2>()
  const visit = (g: Group) => {
    const mark = state.get(g.id)
    if (mark) {
      if (mark === 1) {
        g.previous = null
      }
      return
    }
    state.set(g.id, 1)
    const parent = g.previous ? byId.get(g.previous) : undefined
    if (parent) {
      visit(parent)
    }
    state.set(g.id, 2)
  }
  for (const g of groups.value) {
    visit(g)
  }
  for (const g of groups.value) {
    const cur = g.subCurrent
    if (cur != null && !byId.has(cur)) {
      g.subCurrent = null
    }
  }
}

// ===== 标签 / 条目的交互 ===== 

export function selectTag(parent: Group | null, tag: Group) {
  currentItemClicked.value = { type: 'tag', item: tag }
  setSelectedChild(parent, tag.id)
  for (const item of tag.tasks) {
    const fid = mkFullId(item.id, item.system)
    if (!(fid in hoverState)) {
      hoverState[fid] = false
    }
  }
}

export async function createGroupAt(parent: Group | null) {
  const name = await prompt('请输入标签名称', '')
  if (name === null || name.trim() === '') {
    return
  }
  const group = makeGroup(name, parent ? parent.id : null)
  groups.value.push(group)
  setSelectedChild(parent, group.id)
}

// 需求 10：shift + “+” 切换搜索框（整行含上下偏移）的显隐
export function toggleSearchVisible(group: Group | null) {
  if (group == null) {
    return
  }
  group.searchVisible = group.searchVisible === false
}

export async function setTaskName(item: Task) {
  const name = await prompt('请输入新名称', item.modifiedName || item.originalName)
  if (name === null) {
    return
  }
  item.modifiedName = name.trim() === '' ? null : name
}

export async function setTagName(item: Group) {
  const result = await editGroup({ name: item.name, captureConditions: item.captureConditions })
  if (result == null) {
    return
  }
  if (result.name === null || result.name === '') {
    return
  }
  item.name = result.name
  item.captureConditions = result.captureConditions
}

export function deleteTask(group: Group, task: Task) {
  if (group.id === 'main') {
    return
  }
  const idx = group.tasks.findIndex(t => taskEqual(t, task))
  if (idx !== -1) {
    group.tasks.splice(idx, 1)
  }
}

export async function removeAfter(group: Group, item: Task) {
  if (group.id === 'main') {
    return
  }
  if (!await confirm('确定要删除所有后续项吗？')) {
    return
  }
  const idx = group.tasks.findIndex(t => taskEqual(t, item))
  if (idx === -1) {
    return
  }
  group.tasks.splice(idx + 1, 2147483647)
}

export async function clickTask(item: Task) {
  currentItemClicked.value = { type: 'list', item }
  await rpc.toTop(item.id, item.system)
}

// ===== 拖拽 ===== 

export function onDragList(item: Task) {
  itemDragging.value = { type: 'list', item }
}
export function onDragTag(item: Group) {
  itemDragging.value = { type: 'tag', item }
}
export function endDrag() {
  itemDragging.value = null
}

// 拖拽 group 到条目上 ⇒ 变成该条所属 group 的下级（需求 3）；拖拽条目 ⇒ 本层内重排
export function dropOnItem(owner: Group, target: Task) {
  const dragging = itemDragging.value
  itemDragging.value = null
  if (!dragging) {
    return
  }
  if (dragging.type == 'tag') {
    attachAsChild(dragging.item as Group, owner)
    return
  }
  moveTaskBefore(owner, dragging.item as Task, target)
}

function moveTaskBefore(owner: Group, source: Task, target: Task) {
  const taskList = owner.tasks
  const idxOld = taskList.findIndex(item => taskEqual(item, source))
  const idxTo = taskList.findIndex(item => taskEqual(item, target))
  if (idxOld === -1 || idxTo === -1 || idxOld === idxTo) {
    return
  }
  taskList.splice(idxTo, 0, taskList[idxOld])
  taskList.splice(idxTo < idxOld ? idxOld + 1 : idxOld, 1)
}

// 落在列表缝隙（ul 背景）上：按 y 坐标找插入点，落在所有可见项之后则追加到末尾
export function dropOnListGap(owner: Group, ul: HTMLElement, clientY: number) {
  const dragging = itemDragging.value
  itemDragging.value = null
  if (!dragging) {
    return
  }
  if (dragging.type == 'tag') {
    attachAsChild(dragging.item as Group, owner)
    return
  }
  const source = dragging.item as Task
  const taskList = owner.tasks
  const lis = Array.from(ul.children).filter(el => el.tagName === 'LI') as HTMLElement[]
  if (lis.length === 0) {
    return
  }
  let insertBeforeVisibleIdx = lis.length
  for (let i = 0; i < lis.length; i++) {
    if (clientY < lis[i].getBoundingClientRect().top) {
      insertBeforeVisibleIdx = i
      break
    }
  }
  const shown = visibleTasks(owner)
  if (insertBeforeVisibleIdx >= shown.length) {
    const idxOld = taskList.findIndex(item => taskEqual(item, source))
    if (idxOld === -1) {
      return
    }
    taskList.splice(idxOld, 1)
    taskList.push(source)
    return
  }
  moveTaskBefore(owner, source, shown[insertBeforeVisibleIdx])
}

// 落到本级标签行的空白处 ⇒ 并入本级（顶层行 ⇒ 回到顶层，需求 6）
export function dropOnTagList(parent: Group | null) {
  const dragging = itemDragging.value
  if (dragging?.type != 'tag') {
    return
  }
  itemDragging.value = null
  const dragged = dragging.item as Group
  if (dragged.id === 'main' || isDescendantOf(parent, dragged)) {
    return
  }
  relocate(dragged, parent, null)
}

export function dragOverItem(event: DragEvent, item: Task) {
  if (itemDragging.value?.type === 'tag' || event.dataTransfer?.types.includes('Files')) {
    event.preventDefault()
  }
  if (event.dataTransfer?.types.includes('Files')) {
    rpc.toTop(item.id, item.system)
  }
}

export function dragOverTag(event: DragEvent, tag: Group, parent: Group | null) {
  event.preventDefault()
  if (event.dataTransfer?.types.includes('Files')) {
    selectTag(parent, tag)
  }
}

export function dragOverInternal(event: DragEvent) {
  if (itemDragging.value) {
    event.preventDefault()
  }
}
