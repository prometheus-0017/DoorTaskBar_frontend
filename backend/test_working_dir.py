import window_proxy
import time

def test_get_process_working_directory():
    """测试获取进程工作目录功能"""
    print("开始测试获取进程工作目录...")
    
    # 获取所有顶层窗口
    top_window = window_proxy.WindowProxy.getTopWindow()
    children = top_window.listChildren()
    
    print(f"找到 {len(children)} 个窗口")
    
    # 测试前几个可见窗口
    test_count = 0
    for window in children[:10]:  # 只测试前10个窗口
        title = window.getTitle()
        if title.strip() == '':
            continue
            
        print(f"\n窗口标题: {title}")
        print(f"窗口类名: {window.getClass()}")
        print(f"进程ID: {window.getProcess()}")
        print(f"进程文件名: {window.getProcessFileName()}")
        print(f"进程路径: {window.getProcessPath()}")
        
        # 测试新的工作目录方法
        try:
            working_dir = window.getProcessWorkingDirectory()
            if working_dir:
                print(f"工作目录: {working_dir}")
            else:
                print("工作目录: 无法获取")
        except Exception as e:
            print(f"获取工作目录时出错: {e}")
            
        test_count += 1
        if test_count >= 5:  # 最多测试5个窗口
            break
            
        time.sleep(0.1)  # 短暂延迟避免过于频繁的调用

if __name__ == "__main__":
    test_get_process_working_directory()