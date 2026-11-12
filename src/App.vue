<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import TextButton from './components/TextButton.vue';
import Twin from './components/Twin.vue';
import GroupView from './components/groupView.vue';
import { config } from './components/config'
import { hostId, prepareRpc, rpc } from './components/rpc'
import { confirm, confirmDialogProps, editData, onConfirmCancel, onConfirmSubmit, onGroupCancel, onGroupSubmit, onTextInputCancel, onTextInputSubmit, showConfirmDialog, showModal, showTextInput, textInputProps } from './components/dialogs'
import {
  appendTaskToGroup,
  currentGroup,
  currentItemClicked,
  currentTaskListShowing,
  deleteGroupWithRehome,
  duplicateGroup,
  getListById,
  globalQueryCursor,
  groups,
  makeGroup,
  mkFullId,
  normalizeGroups,
  setTagName,
  setTaskName,
  type ItemProxy,
} from './components/groupStore'
import type { Group, Task } from './components/group'

let shouldTrim = computed(() => {
  return config.shouldTrim;
});
function switchShouldTrim() {
  config.shouldTrim = !config.shouldTrim
}

function switchNightMode() {
  const seq = ['light', 'dark', 'system']
  config.nightMode = seq[(seq.indexOf(config.nightMode) + 1) % seq.length]
  applyTheme(config.nightMode)
}
function switchAddToCurrentGroup() {
  if (config.addToCurrentGroup) {
    config.addToCurrentGroup = false
  } else {
    config.addToCurrentGroup = true
  }
}

// ===== 状态定义 ===== 
const isWideMode = ref(true);
const ready = ref(false)
const saveFinSign = ref('存')
let saveInterval: number | null = null

import EditGroup from './components/editGroup.vue';
import TextInput from './components/TextInput.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';

// 应用主题的核心函数
const applyTheme = (theme: string) => {
  const root = document.documentElement;

  // 先清除可能存在的旧主题类
  root.classList.remove('dark', 'light');

  if (theme === 'dark') {
    root.classList.add('dark');
  } else if (theme === 'light') {
    root.classList.add('light');
  }
  // 如果是 'system'，则不加任何类，让 CSS 的 @media 查询自动接管
};

// 复制当前组（Ctrl+D）：复制名称/捕获规则/任务列表，新组插到原组后面并切换过去
// 只复制组本身：克隆子树会让两个组声称同一批下级，id 引用无法复制
async function handleKeyDown(e: KeyboardEvent) {
  if (e.key == 'w' && e.ctrlKey) {
    if (currentTaskListShowing.value == 'main') {
      return
    }
    if (!await confirm('确定要删除吗？')) {
      return
    }
    deleteGroupWithRehome(currentTaskListShowing.value)
  }
  // 复制当前组（Ctrl+D）
  if (e.key == 'd' && e.ctrlKey) {
    e.preventDefault()
    if (currentTaskListShowing.value == 'main') {
      return
    }
    const src = currentGroup()
    if (src) {
      duplicateGroup(src)
    }
  }
  if (e.key === 'F2') {
    const clicked: ItemProxy | null = currentItemClicked.value
    if (clicked == null) {
      return
    }
    if (clicked.type === 'list') {
      setTaskName(clicked.item as Task)
    } else {
      setTagName(clicked.item as Group)
    }
  }
}

interface WindowChangeInfo {
  type: 'add' | 'change' | 'delete'
  data: Task
}

// 匹配 task 与 group 的捕获规则，返回第一条命中的规则索引，无命中返回 -1
function matchCaptureRule(task: Task, group: Group): number {
  const conditions = group.captureConditions || []
  for (let i = 0; i < conditions.length; i++) {
    const condition = conditions[i]
    let val = null
    //第i条条件,类型为expression时候,走此分支
    if (condition.type == 'expression') {
      try {
        const expression = condition.value
        const evalTarget = { ...task, name: task.modifiedName || task.originalName }

        let f = new Function('item', 'include', 'key', 'return (' + expression + ')')//不安全
        const include = (s: string, sub: string) => s?.toLowerCase().includes(sub?.toLowerCase())
        const key = (testStr: string) => include(evalTarget.name, testStr) || include(evalTarget.processName, testStr)
        if (f(evalTarget, include, key)) {
          return i
        }
      } catch (e) {//todo 这么写实际上根本不会暴露出来
        console.error(e)
        continue
      }
    } else if (condition.type == 'name') {
      //todo 你他妈的远程哪有modify？
      val = task.modifiedName
    } else if (condition.type == 'originName') {
      val = task.originalName
    } else if (condition.type == 'pwd') {
      val = task.pwd
    } else {
      console.warn('未知的condition.type')
    }
    if (val != null &&
      condition.value != '' &&
      val.toLowerCase().includes(condition.value.toLowerCase())) {
      return i
    }
  }
  return -1
}

// 计算按捕获规则顺序对齐后的插入位置：
// 对组内任务的规则归属序列与规则索引序列[0..n-1]求最长公共子序列(LCS)建立映射，
// 一条规则可能连续对应一组任务，新条目应插到该组最后一个匹配任务之后；
// 该规则没有匹配时，插到前一条有匹配规则的对应位置之后；
// 之前也没有匹配时，插到后一条有匹配规则的连续段之前；全无匹配时退化为追加到末尾
function findCaptureInsertPos(group: Group, ruleIdx: number): number {
  const n = (group.captureConditions || []).length
  const tasks = group.tasks
  const m = tasks.length
  const capIdx = group.captureIndex || {}
  const A = tasks.map(t => {
    const idx = capIdx[mkFullId(t.id, t.system)]
    return (typeof idx == 'number' && idx >= 0 && idx < n) ? idx : -1
  })
  // matchRule[q]: 规则 q 在 A 中的 LCS 匹配点，-1 表示无匹配
  const matchRule: number[] = new Array(n).fill(-1)
  if (n > 0 && m > 0) {
    const dp: number[][] = Array.from({ length: m + 1 }, (): number[] => new Array(n + 1).fill(0))
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (A[i - 1] == j - 1) {
          dp[i][j] = dp[i - 1][j - 1] + 1
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
        }
      }
    }
    let i = m, j = n
    while (i > 0 && j > 0) {
      if (A[i - 1] == j - 1) {
        matchRule[j - 1] = i - 1
        i--; j--
      } else if (dp[i - 1][j] >= dp[i][j - 1]) {
        i--
      } else {
        j--
      }
    }
  }
  // 匹配点向两侧扩展成连续段：一条规则连续对应的一组任务
  const segStart: number[] = new Array(n).fill(-1)
  const segEnd: number[] = new Array(n).fill(-1)
  for (let q = 0; q < n; q++) {
    const p = matchRule[q]
    if (p < 0) { continue }
    let lo = p, hi = p
    while (lo > 0 && A[lo - 1] == q) { lo-- }
    while (hi < m - 1 && A[hi + 1] == q) { hi++ }
    segStart[q] = lo
    segEnd[q] = hi
  }
  if (segEnd[ruleIdx] >= 0) {
    return segEnd[ruleIdx] + 1
  }
  for (let q = ruleIdx - 1; q >= 0; q--) {
    if (segEnd[q] >= 0) {
      return segEnd[q] + 1
    }
  }
  for (let q = ruleIdx + 1; q < n; q++) {
    if (segStart[q] >= 0) {
      return segStart[q]
    }
  }
  return tasks.length
}

// 把 task 捕获进 group：已在组内则跳过，命中规则时按规则对齐位置插入并记录归属
function captureIntoGroup(task: Task, group: Group) {
  const fid = mkFullId(task.id, task.system)
  for (let t of group.tasks) {
    if (mkFullId(t.id, t.system) == fid) {
      return
    }
  }
  const ruleIdx = matchCaptureRule(task, group)
  if (ruleIdx < 0) {
    return
  }
  const capIdx = group.captureIndex || (group.captureIndex = {})
  const pos = findCaptureInsertPos(group, ruleIdx)
  group.tasks.splice(pos, 0, task)
  capIdx[fid] = ruleIdx
}

async function saveStatus() {
  let status = {
    config: config,
    taskLists: groups.value
  }
  if (saveInterval !== null) {
    clearInterval(saveInterval)
  }
  saveFinSign.value = '〇'
  await rpc.saveStatus(status)
  saveFinSign.value = '√'
  saveInterval = setInterval(() => saveFinSign.value = '存', 500)
}
async function softSave() {
  let status = {
    config: config,
    taskLists: groups.value
  }
  await rpc.softSave(status)
}
let globalQuery = computed(() => {
  return config.globalQuery
})
function switchGlobalSearchQuery() {
  const current = currentGroup()
  if (!globalQuery.value && current) {
    // 打开共用模式时，把当前 group 的搜索串搬进全局游标
    globalQueryCursor.searchQuery = current.searchQuery
  }
  config.globalQuery = !globalQuery.value
}
function exit() {
  rpc.exit()
}

let taskMap: Map<string, Task> = new Map()

onMounted(async () => {
  await prepareRpc()
  const initData = await rpc.loadStatus()
  if (initData == null) {
    let windowList = await rpc.sync()
    const main = makeGroup('main', null, windowList)
    main.id = 'main'
    groups.value.push(main)
    taskMap = new Map(windowList.map((item: Task) => [mkFullId(item.id, item.system), item]))
  } else {
    Object.assign(config, initData.config)
    groups.value = initData.taskLists
    // 旧 status.json 没有 previous/视图字段，这里补齐并自愈坏数据
    normalizeGroups()
    const initMainCopy = groups.value.find(x => x.id == 'main')?.tasks.concat([]) ?? [];
    let windowList = getListById('main')
    taskMap = new Map(windowList!.map((item: Task) => [mkFullId(item.id, item.system), item]))
    let syncData = await rpc.sync()
    let vis: Map<string, boolean> = new Map()
    for (let _item of syncData) {
      let item: Task = _item
      let localItem = taskMap.get(mkFullId(item.id, item.system))
      if (!localItem) {
        taskMap.set(mkFullId(item.id, item.system), item)
        getListById('main')!.push(item)
      } else {
        localItem.originalName = item.originalName
        localItem.originalIcon = item.originalIcon
        //先这样吧,正常应该icon持久化,但是好像realtime的icon会变化
        localItem.modifiedIcon = item.originalIcon
        // 先这么办但是我觉得不适这么给事情，chrome 插件重启systemid会变化，结果这里还没有判system按道理task的id应该就足够是唯一的但是totop机制又让id从外部生成可能后续接入的system应该改这个id来源
        localItem.system = item.system
        vis.set(mkFullId(item.id, localItem.system), true)
      }
    }
    for (let item of initMainCopy) {
      if (!vis.has(mkFullId(item.id, item.system))) {
        taskMap.delete(mkFullId(item.id, item.system))
      }
    }
    //byd 反序列化之前这个item其实是有引用构成的一个有向无环图的，但是序列化的时候把它完全展开了。导致tag里的item变成了一个副本。
    groups.value.forEach(tag => {
      const originTask = tag.tasks
      tag.tasks = []
      for (let item of originTask) {
        const localItem = taskMap.get(mkFullId(item.id, item.system))
        if (localItem) {
          tag.tasks.push(localItem)
        }
      }
    })

    await rpc.pin(config.pin)
    await rpc.setAllowRemote(config.allowRemote)
  }
  ready.value = true

  // 每5分钟软保存
  setInterval(softSave, 5 * 60 * 1000)

  window.addEventListener('keydown', handleKeyDown);
  setInterval(async () => {
    if (!await rpc.checkLogin(hostId)) {
      await rpc.setCallback(hostId, (updateInfos: Array<WindowChangeInfo>) => {
        for (let updateInfo of updateInfos) {
          switch (updateInfo.type) {
            case 'add':
              taskMap.set(mkFullId(updateInfo.data.id, updateInfo.data.system), updateInfo.data)
              getListById('main')?.push(updateInfo.data)
              // 嵌套的 group 也在同一个扁平数组里，捕获规则对所有层级生效
              for (let group of groups.value) {
                if (group.id == 'main') {
                  continue
                }
                // 新增窗口时按捕获规则对齐位置插入（内部已去重）
                captureIntoGroup(updateInfo.data, group)
              }
              // 需求 7：追加到最下层的 group
              const current = currentGroup()
              if (current && config.addToCurrentGroup) {
                appendTaskToGroup(updateInfo.data, current)
              }
              break
            case 'change': {
              let item = updateInfo.data
              let task = taskMap.get(mkFullId(item.id, item.system))
              if (!task) {
                console.warn('taskMap.get(id)==null')
              } else {
                task.originalName = item.originalName
                task.originalIcon = item.originalIcon
                if (item.pwd != null) {
                  task.pwd = item.pwd
                }
                // 数值变动时重新评估捕获规则，让变动后符合规则的窗口也能被捕获进组（已在组内的不重复）
                for (let group of groups.value) {
                  if (group.id == 'main') {
                    continue
                  }
                  captureIntoGroup(task, group)
                }
              }
              break
            }
            case 'delete':
              taskMap.delete(mkFullId(updateInfo.data.id, updateInfo.data.system))
              break
          }
        }
        let removedFullIds = new Set(updateInfos.filter(x => x.type == 'delete').map(x => mkFullId(x.data.id, x.data.system)))
        groups.value.forEach(tag => {
          tag.tasks = tag.tasks.filter(originItem => !removedFullIds.has(mkFullId(originItem.id, originItem.system)))
          if (tag.captureIndex) {
            for (let fid of removedFullIds) {
              delete tag.captureIndex[fid]
            }
          }
        })
        return '';// 返回undef不应该出发这么傻逼的报错
      })
    }
  }, 500)
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown);
});
let pin = computed(() => {
  return config.pin
})
let allowRemote = computed(() => {
  return config.allowRemote
})
async function togglePin() {
  let pinValue = await rpc.pin(!pin.value)
  config.pin = pinValue
}
async function toggleAllowRemote() {
  let allowRemoteValue = await rpc.setAllowRemote(!allowRemote.value)
  config.allowRemote = allowRemoteValue
}
async function collapse() {
  await rpc.collapse()
}
function refresh() {
  location.reload()
}
</script>

<template>
  <div class="component-container" :class="{ narrow: !isWideMode,'background':true }" @drop.prevent="()=>{console.log('hhhh')}" v-if="ready">
    <!-- 第0行：按钮 -->
    <twin style="height: 30px;">
      <span>
        <text-button @click="collapse" :tooltip="'收回任务栏'"><</text-button>
        <text-button @click="refresh" :tooltip="'刷新'">刷</text-button>
        <text-button @click="togglePin" :tooltip="pin?'当前鼠标移出后任务栏不会自动收回':'当前鼠标移出后任务栏会自动收回'">{{ pin?'定':'动' }}</text-button>
        <text-button @click="toggleAllowRemote" :tooltip="allowRemote?'当前允许远程控制':'当前不允许远程控制'">{{ allowRemote?'远':'关' }}</text-button>
        <text-button @click="switchGlobalSearchQuery" :tooltip="globalQuery?'当前任务栏共用一个搜索条件':'当前每个任务栏使用独立的搜索条件'">{{ globalQuery?'共':'单' }}</text-button>
        <text-button @click="switchShouldTrim" :tooltip="shouldTrim?'当前搜索会去掉首尾空格':'当前搜索不会去掉首尾空格'">{{ shouldTrim?'修':'留' }}</text-button>
        <text-button @click="switchNightMode" :tooltip="{light:'当前是亮色主题',dark:'当前是暗色主题',system:'主题当前跟随系统'}[config.nightMode]">{{ {light:'日',dark:'夜',system:'随'}[config.nightMode] }}</text-button>
        <text-button @click="switchAddToCurrentGroup" :tooltip="config.addToCurrentGroup?'当前会追加到当前目录':'当前不追加到当前目录'">{{ config.addToCurrentGroup?'追':'无' }}</text-button>

        <text-button @click="saveStatus" :tooltip="'保存当前配置'">{{ saveFinSign }}</text-button>
      </span>

      <text-button @click="exit" v-if="isWideMode">x</text-button>
    </twin>

    <!-- 标签行/搜索框/条目列表/下级容器全部由递归的 groupView 负责 -->
    <GroupView :parent="null" :is-wide-mode="isWideMode" />

    <EditGroup
      v-if="showModal"
      :initial-data="editData"
      @cancel="onGroupCancel"
      @submit="onGroupSubmit"
    />
    <TextInput
      v-if="showTextInput"
      :title="textInputProps.title"
      :default-value="textInputProps.defaultValue"
      :placeholder="textInputProps.placeholder"
      @cancel="onTextInputCancel"
      @submit="onTextInputSubmit"
    />
    <ConfirmDialog
      v-if="showConfirmDialog"
      :title="confirmDialogProps.title"
      @cancel="onConfirmCancel"
      @submit="onConfirmSubmit"
    />
  </div>
</template>

<style scoped>
.component-container {
  margin: 0 auto;
  width: 300px;
  height: 95vh;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  border: 0px solid #ccc;
  padding: 10px;
}

.component-container.narrow {
  width: 50px;
}

.background {
  background-color: var(--background-color);
  color: var(--text-color);
}
</style>
