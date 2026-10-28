
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
