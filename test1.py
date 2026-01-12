# test_script.py - 用于测试的性能脚本
import time
import math

def heavy_calculation():
    """一个计算密集的函数"""
    result = 0
    for i in range(1000000):
        result += math.sqrt(i) * math.sin(i)
    return result

def memory_intensive():
    """内存密集型操作"""
    data = []
    for i in range(10000):
        data.append([j for j in range(1000)])
    return sum(len(x) for x in data)

def main():
    print("开始性能测试...")
    
    # CPU密集型
    start = time.time()
    result1 = heavy_calculation()
    print(f"计算完成: {result1:.2f}, 耗时: {time.time()-start:.2f}秒")
    
    # 内存密集型
    start = time.time()
    result2 = memory_intensive()
    print(f"内存操作完成: {result2}, 耗时: {time.time()-start:.2f}秒")
    
    print("测试完成!")

if __name__ == "__main__":
    main()