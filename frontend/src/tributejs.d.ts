declare module 'tributejs' {
  export interface TributeItem {
    key: string;
    value: string;
    description?: string;
    [k: string]: any;
  }

  export interface TributeCollection<T extends TributeItem = TributeItem> {
    trigger: string;
    requireLeadingSpace?: boolean;
    values: T[] | ((text: string, cb: (items: T[]) => void) => void);
    lookup: string;
    fillAttr: string;
    selectTemplate?: (item: { original: T; string?: string }) => string;
    menuItemTemplate?: (item: { original: T; string?: string }) => string;
    menuShowMinLength?: number;
  }

  export interface TributeOptions<T extends TributeItem = TributeItem> {
    collection: TributeCollection<T> | TributeCollection<T>[];
    allowSpaces?: boolean;
    autocompleteMode?: boolean;
    positionMenu?: boolean;
    containerClass?: string;
    noMatchTemplate?: (() => string) | string;
  }

  export default class Tribute<T extends TributeItem = TributeItem> {
    constructor(options: TributeOptions<T>);
    collection: TributeCollection<T>[];
    isActive: boolean;
    attach(element: HTMLElement): void;
    detach(element: HTMLElement): void;
    showMenuForCollection(element: HTMLElement, collectionIndex: number): void;
    hideMenu(): void;
  }
}
