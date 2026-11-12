
export interface Group {
  id: string;
  name: string;
  scrollStatus:number;
  searchQuery: string;
    captureConditions: CaptureCondition[];
  tasks: Task[];
  // 记录组内每个任务由哪条捕获规则捕获进来：key 为 mkFullId(task.id,task.system)，value 为 captureConditions 的索引
  // 用于把新捕获的任务按规则顺序对齐插入；历史数据/手动加入的任务没有记录，视为无归属(-1)
  captureIndex?: Record<string, number>;
  // 父 group 的 id，null 表示顶层 group。必填，好让类型检查逼出所有 group 构造点
  previous: string | null;
  // 本级当前选中的子 group id；缺失时回退到第一个子 group
  subCurrent?: string | null;
  // 下级容器在剩余高度中的占比，默认 0.5（下级 group 与 item 各占一半）
  subRatio?: number;
  // 展示该 group 时是否显示搜索框，默认 true，由 shift + “+” 切换
  searchVisible?: boolean;
}
// 数据模型
export interface Task {
  id: number;
  system:string;
  pwd:string;
  processId?:number
  processName: string;
  originalName: string;
  modifiedName: string|null;
  originalIcon: string;
  modifiedIcon: string|null;
}
// 类型定义
export interface CaptureCondition {
  type: 'expression';
  value: string;
}
export interface editableGroup{
    name:string
    captureConditions: CaptureCondition[];
}
