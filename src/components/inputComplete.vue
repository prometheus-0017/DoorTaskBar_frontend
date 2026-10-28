<!-- ExpressionAutocomplete.vue -->
<template>
  <div class="expression-autocomplete">
    <label v-if="label" class="expression-label">{{ label }}</label>
    <input
      ref="inputRef"
      v-model="expression"
      :placeholder="placeholder"
      class="expression-input"
      @input="onInput"
      @keydown="onKeydown"
    />
    <!-- 当前解析出的上下文信息（调试用，可移除） -->
    <div v-if="debug" class="debug-info">
      <span>context: {{ contextInfo.type }}</span>
      <span>property: {{ contextInfo.property }}</span>
      <span>partial: {{ contextInfo.partial }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import Tribute from 'tributejs'
import type { TributeItem } from 'tributejs'

// ============================================================
// Props & Emits
// ============================================================
interface Props {
  /** 输入标签 */
  label?: string
  /** 占位符 */
  placeholder?: string
  /** 初始值 */
  modelValue?: string
  /** 属性名称枚举列表 */
  propertyList?: string[]
  /**
   * 根据属性名计算字面量候选列表的函数（异步，支持流控）
   * 签名: (propertyName: string) => Promise<string[]>
   * 后续可在此函数内加 debounce / throttle / 缓存 / 请求取消等流控逻辑
   */
  computeLiterals?: ((propertyName: string) => Promise<string[]>) | null
  /** 是否显示调试信息 */
  debug?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  placeholder: "item.processName=='chrome' && item.pwd=='/home'",
  modelValue: '',
  propertyList: () => [
    'id',
    'system',
    'pwd',
    'processId',
    'processName',
    'originalName',
    'modifiedName',
    'originalIcon',
    'modifiedIcon',
  ],
  computeLiterals: null,
  debug: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
}>()

// ============================================================
// 上下文类型
// ============================================================
type ContextType =
  | 'variable'
  | 'property'
  | 'literal'
  | 'literal_pending'
  | 'none'

interface ContextInfo {
  type: ContextType
  /** 当前正在补全字面量对应的属性名 */
  property: string
  /** 光标前正在输入的片段 */
  partial: string
}

// ============================================================
// 响应式状态
// ============================================================
const inputRef = ref<HTMLInputElement | null>(null)
const expression = ref<string>(props.modelValue)
let tribute: Tribute | null = null

/** 当前光标位置的上下文 */
const contextInfo = ref<ContextInfo>({
  type: 'none',
  property: '',
  partial: '',
})

// ============================================================
// 默认字面量计算函数（当 props.computeLiterals 未提供时使用）
// TODO: 后续在这里接入流控（debounce / requestQueue / AbortController）
// ============================================================
const defaultComputeLiterals = async (propertyName: string): Promise<string[]> => {
  // 模拟异步获取，实际可替换为 API 请求
  // 字段对齐 Task 接口（见 group.ts）
  const literalMap: Record<string, string[]> = {
    system: ['windows', 'linux', 'macos'],
    pwd: ['/home', '/usr/local', '/opt', 'C:\\Users', 'C:\\Program Files'],
    processId: ['1000', '2000', '3000'],
    processName: ['chrome', 'firefox', 'code', 'node', 'explorer'],
    originalName: ['chrome', 'firefox', 'code', 'node', 'explorer'],
    modifiedName: ['null', 'my-chrome', 'my-firefox'],
    originalIcon: ['default', 'custom'],
    modifiedIcon: ['null', 'custom-icon'],
    id: ['1', '2', '3'],
  }
  return literalMap[propertyName] || []
}

/**
 * 获取字面量列表（统一入口，方便后续加流控）
 * 后续流控方案示例：
 *   - 用 AbortController 取消上一次请求
 *   - 用 debounce 延迟触发
 *   - 用 Map 做结果缓存
 *   - 用信号量限制并发数
 */
let _lastAbortController: AbortController | null = null
const getLiteralValues = async (propertyName: string): Promise<string[]> => {
  // 取消上一次进行中的计算
  if (_lastAbortController) {
    _lastAbortController.abort()
  }
  _lastAbortController = new AbortController()

  try {
    const fn = props.computeLiterals || defaultComputeLiterals
    const result = await fn(propertyName)
    return result || []
  } catch (e: unknown) {
    const err = e as { name?: string }
    if (err.name === 'AbortError') return []
    console.warn('[ExpressionAutocomplete] computeLiterals error:', e)
    return []
  }
}

// ============================================================
// 核心：上下文解析器：分析光标前文本，判断当前应补全什么
// ============================================================
const parseContext = (textBeforeCursor: string): ContextInfo => {
  const trimmed = textBeforeCursor.trimEnd()

  // 场景 1：光标前是 item. 后面正在输入属性名
  //   匹配: "item.na" / "item." / "item.n" / "...&& item.pa"
  const propertyMatch = trimmed.match(/item\.(\w*)$/)
  if (propertyMatch !== null) {
    return {
      type: 'property',
      property: '',
      partial: propertyMatch[1] || '',
    }
  }

  // 场景 2：光标前是 item.xxx==' 或 item.xxx=" 后面正在输入字面量
  //   匹配: "item.name=='chr" / "item.path='/op"
  const literalMatch = trimmed.match(/item\.(\w+)\s*==\s*['"]([^'"]*)$/)
  if (literalMatch !== null) {
    return {
      type: 'literal',
      property: literalMatch[1],
      partial: literalMatch[2] || '',
    }
  }

  // 场景 3：光标前在输入变量名 item（可能是开头、&&后、||后、空格后）
  //   匹配: "" / "i" / "it" / "ite" / "&& i" / "&& it"
  const variableMatch = trimmed.match(/(?:^|[(&|,;\s])\s*(i(t(e(m)?)?)?)$/)
  if (variableMatch !== null) {
    return {
      type: 'variable',
      property: '',
      partial: variableMatch[1] || '',
    }
  }

  // 场景 4：光标前刚输入了 == 或 = 后面，可能需要补全字面量（无引号情况）
  //   匹配: "item.name==" / "item.name="
  const operatorMatch = trimmed.match(/item\.(\w+)\s*={1,2}\s*$/)
  if (operatorMatch !== null) {
    return {
      type: 'literal_pending',
      property: operatorMatch[1],
      partial: '',
    }
  }

  return { type: 'none', property: '', partial: '' }
}

// ============================================================
// Tribute.js 初始化
// ============================================================
const initTribute = () => {
  if (!inputRef.value) return

  tribute = new Tribute({
    collection: [
      // ---- Collection 0: 变量补全 (item) ----
      // 用一个不可能出现的字符做占位 trigger，实际由程序化触发
      {
        trigger: '\x01', // 不可见字符，防止自然触发
        requireLeadingSpace: false,
        values: [
          { key: 'item', value: 'item', description: '变量 - 数据项' },
        ],
        lookup: 'key',
        fillAttr: 'value',
        selectTemplate: (item) => {
          // 替换掉当前 partial 部分
          return item.original.value
        },
        menuItemTemplate: (item) => {
          return `<div class="tribute-item">
            <span class="tribute-item-key">${item.original.key}</span>
            <span class="tribute-item-desc">${item.original.description}</span>
          </div>`
        },
        menuShowMinLength: 0,
      },

      // ---- Collection 1: 属性名补全 (item.xxx) ----
      {
        trigger: '\x02',
        requireLeadingSpace: false,
        values: props.propertyList.map<TributeItem>((name) => ({
          key: name,
          value: name,
          description: `属性 - ${name}`,
        })),
        lookup: 'key',
        fillAttr: 'value',
        selectTemplate: (item) => {
          return item.original.value
        },
        menuItemTemplate: (item) => {
          return `<div class="tribute-item tribute-property">
            <span class="tribute-item-key">.${item.original.key}</span>
            <span class="tribute-item-desc">${item.original.description}</span>
          </div>`
        },
        menuShowMinLength: 0,
      },

      // ---- Collection 2: 字面量补全 ('value') ----
      {
        trigger: '\x03',
        requireLeadingSpace: false,
        values: [], // 动态填充
        lookup: 'key',
        fillAttr: 'value',
        selectTemplate: (item) => {
          return `'${item.original.value}'`
        },
        menuItemTemplate: (item) => {
          return `<div class="tribute-item tribute-literal">
            <span class="tribute-item-key">'${item.original.key}'</span>
            <span class="tribute-item-desc">字面量</span>
          </div>`
        },
        menuShowMinLength: 0,
      },
    ],

    // 全局配置
    allowSpaces: false,
    autocompleteMode: false,
    positionMenu: true,
    containerClass: 'expression-tribute-container',
    noMatchTemplate: () => '<span class="tribute-no-match">无匹配项</span>',
  })

  tribute.attach(inputRef.value)

  // 监听 Tribute 选择事件
  inputRef.value.addEventListener('tribute-replaced', () => {
    const value = inputRef.value!.value
    expression.value = value
    emit('update:modelValue', value)
    emit('change', value)
  })

  // 监听 Tribute 的 active 状态变化
  inputRef.value.addEventListener('tribute-active', () => {
    // menu opened
  })
  inputRef.value.addEventListener('tribute-inactive', () => {
    // menu closed
  })
}

// ============================================================
// 核心：input 事件处理 — 解析上下文 & 程序化触发补全
// ============================================================
const onInput = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const cursorPos: number = input.selectionStart ?? 0
  const textBeforeCursor = input.value.substring(0, cursorPos)

  const ctx = parseContext(textBeforeCursor)
  contextInfo.value = ctx

  // 先隐藏已有菜单
  if (tribute && tribute.isActive) {
    tribute.hideMenu()
  }

  await nextTick()

  switch (ctx.type) {
    case 'variable':
      // 触发变量补全 (Collection 0)
      showCollection(0, ctx.partial)
      break

    case 'property':
      // 触发属性补全 (Collection 1)
      showCollection(1, ctx.partial)
      break

    case 'literal':
      // 触发字面量补全 (Collection 2) — 需要先异步获取候选列表
      await updateLiteralValues(ctx.property)
      showCollection(2, ctx.partial)
      break

    case 'literal_pending':
      // 刚输入 ==，自动插入引号并触发字面量补全
      insertQuoteAndShowLiteral(ctx.property, cursorPos)
      break

    default:
      // 不做任何补全
      break
  }

  // 同步值
  expression.value = input.value
  emit('update:modelValue', input.value)
}

/**
 * 程序化显示指定 collection 的菜单
 *
 * 注意：我们的三个 collection 使用的是不可见控制字符（\x01 / \x02 / \x03）
 * 作为 trigger，输入框里并不存在这些字符。如果调用 Tribute 原生的
 * showMenuForCollection，它会从光标位置向前搜索 trigger，找不到时部分
 * 版本会把 trigger 字符作为占位塞进 input.value，导致出现奇怪的符号，
 * 并且让 Tribute 的内部状态与输入框真实内容错位，后续退格/输入都会被
 * Tribute 的 keydown 监听器错误处理。
 *
 * 因此程序化触发一律走我们自己的 manualShowMenu，完全绕开 Tribute 的
 * trigger 查找逻辑，避免污染输入框内容。
 */
const showCollection = (collectionIndex: number, partialText: string) => {
  if (!tribute || !inputRef.value) return
  // 先确保 Tribute 原生菜单处于关闭状态，防止残留
  if (tribute.isActive) {
    tribute.hideMenu()
  }
  manualShowMenu(collectionIndex, partialText)
}

/**
 * 手动显示菜单（处理 Tribute 程序化触发的兼容问题）
 * 当 Tribute 的 trigger 是不可见字符时，showMenuForCollection
 * 可能无法正确找到 trigger 位置，需要手动干预
 */
const manualShowMenu = (collectionIndex: number, partialText: string) => {
  if (!tribute || !inputRef.value) return

  const collection = tribute.collection[collectionIndex]
  const rawValues = collection.values
  if (typeof rawValues !== 'object' || !Array.isArray(rawValues)) return
  const values = rawValues as TributeItem[]

  // 获取当前输入值，找到需要替换的区间
  const input = inputRef.value
  const cursorPos: number = input.selectionStart ?? 0
  const textBeforeCursor = input.value.substring(0, cursorPos)
  void textBeforeCursor

  // 计算当前 partial 的起始位置
  const replaceStart = cursorPos - (partialText ? partialText.length : 0)

  // 过滤候选值
  const filtered = values.filter((item) => {
    const key: string = (item as any)[collection.lookup] || item.key || ''
    return key.toLowerCase().startsWith((partialText || '').toLowerCase())
  })

  if (filtered.length === 0) {
    tribute.hideMenu()
    return
  }

  // 手动构建菜单
  showCustomMenu(filtered, collection, replaceStart, cursorPos)
}

/**
 * 自定义菜单渲染（当 Tribute 原生程序化触发不可靠时的备选方案）
 */
interface CustomMenuState {
  el: HTMLUListElement
  selectedIndex: number
  items: TributeItem[]
  keyHandler: ((e: KeyboardEvent) => void) | null
  outsideClickHandler: ((e: MouseEvent) => void) | null
}

let customMenuEl: CustomMenuState | null = null

const showCustomMenu = (
  items: TributeItem[],
  collection: any,
  replaceStart: number,
  replaceEnd: number,
) => {
  hideCustomMenu()

  const ul = document.createElement('ul')
  ul.className = 'expression-tribute-container custom-tribute-menu'

  const state: CustomMenuState = {
    el: ul,
    selectedIndex: 0,
    items,
    keyHandler: null,
    outsideClickHandler: null,
  }
  customMenuEl = state

  const renderItems = () => {
    ul.innerHTML = ''
    items.forEach((item, index) => {
      const li = document.createElement('li')
      li.className = `tribute-item${index === state.selectedIndex ? ' highlight' : ''}`
      li.innerHTML = collection.menuItemTemplate({
        original: item,
        string: item[collection.lookup] || item.key,
      })
      li.addEventListener('mousedown', (e) => {
        e.preventDefault()
        selectItem(item, collection, replaceStart, replaceEnd)
      })
      ul.appendChild(li)
    })
  }

  renderItems()

  // 定位菜单
  const input = inputRef.value!
  const rect = input.getBoundingClientRect()
  ul.style.position = 'absolute'
  ul.style.left = `${rect.left + window.scrollX}px`
  ul.style.top = `${rect.bottom + window.scrollY}px`
  ul.style.width = `${Math.max(rect.width, 250)}px`
  ul.style.zIndex = '30000'

  document.body.appendChild(ul)

  // 键盘导航
  const keyHandler = (e: KeyboardEvent) => {
    if (!customMenuEl) {
      document.removeEventListener('keydown', keyHandler, true)
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        state.selectedIndex = (state.selectedIndex + 1) % items.length
        renderItems()
        break
      case 'ArrowUp':
        e.preventDefault()
        state.selectedIndex = (state.selectedIndex - 1 + items.length) % items.length
        renderItems()
        break
      case 'Enter':
      case 'Tab':
        e.preventDefault()
        selectItem(items[state.selectedIndex], collection, replaceStart, replaceEnd)
        document.removeEventListener('keydown', keyHandler, true)
        break
      case 'Escape':
        e.preventDefault()
        hideCustomMenu()
        document.removeEventListener('keydown', keyHandler, true)
        break
    }
  }
  state.keyHandler = keyHandler

  document.addEventListener('keydown', keyHandler, true)

  // 点击外部关闭
  const outsideClickHandler = (e: MouseEvent) => {
    if (
      customMenuEl &&
      !customMenuEl.el.contains(e.target as Node) &&
      e.target !== inputRef.value
    ) {
      hideCustomMenu()
      document.removeEventListener('click', outsideClickHandler)
      document.removeEventListener('keydown', keyHandler, true)
    }
  }
  state.outsideClickHandler = outsideClickHandler

  setTimeout(() => {
    document.addEventListener('click', outsideClickHandler)
  }, 0)
}

const selectItem = (
  item: TributeItem,
  collection: any,
  replaceStart: number,
  replaceEnd: number,
) => {
  const input = inputRef.value!
  const text = input.value

  // 使用 selectTemplate 获取插入文本
  const insertText: string = collection.selectTemplate({
    original: item,
    string: item[collection.lookup] || item.key,
  })

  // 替换文本
  const before = text.substring(0, replaceStart)
  const after = text.substring(replaceEnd)
  input.value = before + insertText + after
  expression.value = input.value

  // 设置光标位置
  const newCursorPos = before.length + insertText.length
  input.setSelectionRange(newCursorPos, newCursorPos)
  input.focus()

  hideCustomMenu()

  emit('update:modelValue', input.value)
  emit('change', input.value)
}

const hideCustomMenu = () => {
  if (customMenuEl) {
    if (customMenuEl.keyHandler) {
      document.removeEventListener('keydown', customMenuEl.keyHandler, true)
    }
    if (customMenuEl.outsideClickHandler) {
      document.removeEventListener('click', customMenuEl.outsideClickHandler)
    }
    if (customMenuEl.el.parentNode) {
      customMenuEl.el.parentNode.removeChild(customMenuEl.el)
    }
    customMenuEl = null
  }
}

/**
 * 动态更新字面量候选列表 (Collection 2)
 */
const updateLiteralValues = async (propertyName: string) => {
  if (!tribute) return
  const literals = await getLiteralValues(propertyName)
  tribute.collection[2].values = literals.map<TributeItem>((val) => ({
    key: val,
    value: val,
    description: `${propertyName} = '${val}'`,
  }))
}

/**
 * 当输入 == 后，自动插入引号并触发字面量补全
 */
const insertQuoteAndShowLiteral = async (propertyName: string, cursorPos: number) => {
  const input = inputRef.value!
  const text = input.value

  // 在光标位置插入引号
  const before = text.substring(0, cursorPos)
  const after = text.substring(cursorPos)
  input.value = before + "'" + after
  const newCursorPos = cursorPos + 1
  input.setSelectionRange(newCursorPos, newCursorPos)

  expression.value = input.value
  emit('update:modelValue', input.value)

  // 触发字面量补全
  await updateLiteralValues(propertyName)
  showCollection(2, '')
}

// ============================================================
// 键盘事件
// ============================================================
const onKeydown = (_e: KeyboardEvent) => {
  // 如果自定义菜单打开着，由菜单的 keyHandler 处理
  // 这里处理 Tribute 原生菜单的情况
}

// ============================================================
// 生命周期
// ============================================================
watch(
  () => props.modelValue,
  (newVal: string) => {
    if (newVal !== expression.value) {
      expression.value = newVal
    }
  },
)

watch(
  () => props.propertyList,
  (newList: string[]) => {
    if (tribute && tribute.collection[1]) {
      tribute.collection[1].values = newList.map<TributeItem>((name) => ({
        key: name,
        value: name,
        description: `属性 - ${name}`,
      }))
    }
  },
  { deep: true },
)

onMounted(() => {
  nextTick(() => {
    initTribute()
  })
})

onBeforeUnmount(() => {
  hideCustomMenu()
  if (tribute && inputRef.value) {
    tribute.detach(inputRef.value)
  }
  if (_lastAbortController) {
    _lastAbortController.abort()
  }
})
</script>

<style>
/* ============================================================
   输入框样式
   ============================================================ */
.expression-autocomplete {
  position: relative;
  width: 100%;
  min-width: 0; /* 关键：作为 flex 子项时允许收缩，否则会把兄弟元素挤出容器 */
}

.expression-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-color);
}

.expression-input {
  width: 100%;
  padding: 4px 8px;
  font-size: 13px;
  font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: var(--background-color);
  color: var(--text-color);
  box-sizing: border-box;
}

.expression-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
  background: var(--highlight-color);
}

/* ============================================================
   Tribute 菜单容器样式
   ============================================================ */
.expression-tribute-container,
.custom-tribute-menu {
  background: var(--background-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  max-height: 220px;
  overflow-y: auto;
  list-style: none;
  padding: 2px 0;
  margin: 2px 0 0 0;
  z-index: 30000;
}

.expression-tribute-container li,
.custom-tribute-menu li {
  list-style: none;
}

/* ============================================================
   菜单项样式
   ============================================================ */
.tribute-item {
  padding: 3px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  transition: background 0.15s;
}

.tribute-item:hover,
.tribute-item.highlight,
.expression-tribute-container li.highlight {
  background: var(--highlight-color);
}

.tribute-item-key {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-weight: 600;
  color: #4338ca;
}

.tribute-item-desc {
  color: var(--text-color);
  opacity: 0.6;
  font-size: 11px;
}

/* 属性补全项 — 绿色 */
.tribute-property .tribute-item-key {
  color: #059669;
}

/* 字面量补全项 — 橙色 */
.tribute-literal .tribute-item-key {
  color: #d97706;
}

/* 无匹配提示 */
.tribute-no-match {
  padding: 4px 8px;
  color: var(--text-color);
  opacity: 0.6;
  font-size: 12px;
  display: block;
}

/* ============================================================
   调试信息
   ============================================================ */
.debug-info {
  margin-top: 8px;
  padding: 6px 10px;
  background: var(--highlight-color);
  border-radius: 6px;
  font-size: 12px;
  font-family: monospace;
  color: var(--text-color);
  display: flex;
  gap: 16px;
}
</style>
