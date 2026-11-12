<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import TextButton from './TextButton.vue'
import Twin from './Twin.vue'
import type { Group, Task } from './group'
import {
  childrenOf,
  clickTask,
  createGroupAt,
  deleteTask,
  dragOverInternal,
  dragOverItem,
  dragOverTag,
  dropOnItem,
  dropOnListGap,
  dropOnTagList,
  dropOnTagTarget,
  endDrag,
  hasChildren,
  hoverState,
  currentItemClicked,
  mkFullId,
  queryCursorFor,
  onDragList,
  onDragTag,
  removeAfter,
  selectTag,
  selectedChild,
  setTaskName,
  toggleSearchVisible,
  taskEqual,
  visibleTasks,
} from './groupStore'

// parent 为 null 表示顶层这一层；本级展示的是 parent 的子 group，递归即由 subarea 里的自身完成
const props = defineProps<{
  parent: Group | null
  isWideMode: boolean
}>()

defineOptions({ name: 'groupView' })

const MIN_PX = 40

const siblings = computed(() => childrenOf(props.parent))
const active = computed(() => selectedChild(props.parent))
const shown = computed(() => (active.value ? visibleTasks(active.value) : []))
const searchCursor = computed(() => (active.value ? queryCursorFor(active.value) : null))
const showSub = computed(() => hasChildren(active.value))
const ratio = computed(() => active.value?.subRatio ?? 0.5)
const listFlex = computed(() => (showSub.value ? `${1 - ratio.value} 1 0px` : '1 1 0px'))
const subFlex = computed(() => `${ratio.value} 1 0px`)

const listEl = ref<HTMLElement | null>(null)
const bodyEl = ref<HTMLElement | null>(null)

// 每一层各自记住自己的滚动位置
let lastActive: Group | null = active.value
watch(active, async (next) => {
  if (lastActive && listEl.value) {
    lastActive.scrollStatus = listEl.value.scrollTop
  }
  lastActive = next
  await nextTick()
  restoreScroll()
})
function restoreScroll() {
  if (listEl.value && active.value) {
    listEl.value.scrollTop = active.value.scrollStatus
  }
}
onMounted(restoreScroll)

const splitMove = (e: MouseEvent) => {
  const body = bodyEl.value
  const g = active.value
  if (!body || !g) {
    return
  }
  const rect = body.getBoundingClientRect()
  const min = MIN_PX / rect.height
  g.subRatio = Math.min(Math.max((e.clientY - rect.top) / rect.height, min), 1 - min)
}
const splitEnd = () => {
  document.removeEventListener('mousemove', splitMove)
  document.removeEventListener('mouseup', splitEnd)
  document.body.style.userSelect = ''
}
function startSplit(event: MouseEvent) {
  if (!bodyEl.value || !active.value) {
    return
  }
  event.preventDefault()
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', splitMove)
  document.addEventListener('mouseup', splitEnd)
}
onBeforeUnmount(splitEnd)

async function onPlusClick(event: MouseEvent) {
  if (event.shiftKey) {
    toggleSearchVisible(active.value)
    return
  }
  await createGroupAt(props.parent)
}

function onSearchInput(event: Event) {
  if (searchCursor.value) {
    searchCursor.value.searchQuery = (event.target as HTMLInputElement).value
  }
}
function clearSearch() {
  if (searchCursor.value) {
    searchCursor.value.searchQuery = ''
  }
}

function onItemDrop(event: DragEvent, item: Task) {
  event.stopPropagation()
  if (active.value) {
    dropOnItem(active.value, item)
  }
}

function onGapDrop(event: DragEvent) {
  if (event.target !== event.currentTarget || !active.value) {
    return
  }
  dropOnListGap(active.value, event.currentTarget as HTMLElement, event.clientY)
}

async function onRightClick(item: Task, event: MouseEvent) {
  if (!active.value) {
    return
  }
  if (event.shiftKey) {
    await removeAfter(active.value, item)
  } else {
    await setTaskName(item)
  }
}

function fid(item: Task) {
  return mkFullId(item.id, item.system)
}
</script>

<template>
  <div class="panel">
    <div v-if="isWideMode" class="row tags-row" @dragover="dragOverInternal($event)" @drop="dropOnTagList(parent)">
      <span class="plus" @click="onPlusClick($event)">+</span>
      <span v-for="tag in siblings"
            :key="tag.id"
            :class="{ active: tag.id === active?.id }"
            draggable="true"
            @click="selectTag(parent, tag)"
            @dragstart="onDragTag(tag)"
            @dragend="endDrag"
            @dragover="dragOverTag($event, tag, parent)"
            @drop.stop="dropOnTagTarget(tag)"
      >{{ tag.name }}</span>
    </div>
    <div v-else class="row current-tag">{{ active?.name }}</div>

    <div v-if="isWideMode && active?.searchVisible !== false" class="row search-box">
      <div class="input-wrapper">
        <input type="text" placeholder="Filter..." :value="searchCursor?.searchQuery ?? ''" @input="onSearchInput" />
        <span v-if="searchCursor?.searchQuery" class="clear-button" @click="clearSearch">×</span>
      </div>
    </div>

    <div class="body" ref="bodyEl">
      <div class="list-container" ref="listEl" :style="{ flex: listFlex }">
        <ul class="item-list" :class="{ wide: isWideMode }" @dragover="dragOverInternal($event)" @drop="onGapDrop">
          <li v-for="item in shown"
              :key="fid(item)"
              :class="{ current: taskEqual(currentItemClicked?.item as Task, item) }"
              :data-item-id="item.id"
              draggable="true"
              @click="clickTask(item)"
              @dragstart="onDragList(item)"
              @dragend="endDrag"
              @dragover="dragOverItem($event, item)"
              @drop="onItemDrop($event, item)"
              @contextmenu.prevent="onRightClick(item, $event)"
              @mouseenter="hoverState[fid(item)] = true"
              @mouseleave="hoverState[fid(item)] = false"
          >
            <Twin style="width: 100%; gap: 8px; align-items: center;">
              <img v-if="isWideMode" :src="item.modifiedIcon || item.originalIcon" alt="" style="width: 24px;height: 24px;flex-shrink: 0;" />
              <span :title="item.processName" v-if="isWideMode" style="flex: 1;text-overflow: ellipsis;text-align: left; word-wrap: break-word; overflow: hidden;height:28px;width:1px">{{ item.modifiedName || item.originalName }}</span>
              <TextButton v-show="isWideMode && active?.id !== 'main'" :class="{ 'delete-btn': !hoverState[fid(item)] }" @click.stop="deleteTask(active!, item)">x</TextButton>
            </Twin>
          </li>
        </ul>
      </div>

      <template v-if="showSub">
        <div class="splitter" @mousedown="startSplit"></div>
        <div class="subarea" :style="{ flex: subFlex }">
          <groupView :parent="active" :is-wide-mode="isWideMode" />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
}

.row {
  margin-bottom: 10px;
  flex: none;
}

.tags-row {
  height: 30px;
  overflow-x: auto;
  white-space: nowrap;
}

.tags-row span {
  cursor: pointer;
  margin-right: 10px;
}

.tags-row .active {
  font-weight: bold;
}

.current-tag {
  height: 30px;
}

.search-box {
  height: 30px;
}

.body {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
}

.list-container {
  display: flex;
  overflow-x: hidden;
  overflow-y: auto;
  min-height: 0;
}

.subarea {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.splitter {
  flex: none;
  height: 6px;
  margin: 2px 0;
  border-radius: 3px;
  background-color: var(--border-color);
  opacity: 0.4;
  cursor: row-resize;
}

.splitter:hover {
  opacity: 1;
}

.item-list {
  padding: 0;
  width: 100%;
}

.item-list.wide {
  display: flex;
  width: 100%;
  flex-direction: column;
  border-radius: 5px;
  gap: 4px;
}

.item-list li {
  display: flex;
  align-items: center;
  height: 34px;
  justify-content: space-between;
  cursor: default;
  padding: 1px 8px;
  margin: 0;
  border-radius: 8px;
  box-sizing: border-box;
}

.item-list.wide li {
  cursor: pointer;
}

.item-list li:hover {
  background-color: var(--highlight-color);
}

.delete-btn {
  visibility: hidden;
}

.item-list li:hover .delete-btn {
  display: inline-block;
  visibility: visible;
}

.current {
  background-color: var(--highlight-color);
}

.list-container img {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  object-fit: contain;
}

.input-wrapper {
  position: relative;
  width: 300px;
  height: 100%;
}

.input-wrapper input {
  width: 100%;
  height: 100%;
  padding: 0 24px 0 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--background-color);
  color: var(--text-color);
  font-size: 13px;
  box-sizing: border-box;
  outline: none;
}

.clear-button {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-color);
  opacity: 0;
  padding: 2px;
  pointer-events: none;
}

.clear-button:hover {
  opacity: 1;
}

.input-wrapper:hover .clear-button,
.input-wrapper input:focus + .clear-button {
  opacity: 1;
  pointer-events: auto;
}
</style>
