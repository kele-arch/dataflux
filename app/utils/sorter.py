# -- coding: utf-8 --
# @Author: 胡H
# @File: app/utils/sorter.py
# @Created: 2025/11/19 16:10
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: 提供排序算法类封装，支持多种排序方式
from typing import List, Optional

from app.com.decorators import measure_time


class Sorter:
    """ Sorter 提供多种排序算法封装:
    - bubble_sort
    - quick_sort
    - selection_sort
    """

    def __init__(self, data: List[int]):
        self.data = data.copy()  # 保留原数据
        self.sorted_data: Optional[List[int]] = None
        self.execution_time: Optional[float] = None

    @measure_time
    def bubble_sort(self) -> List[int]:
        """冒泡排序"""
        arr = self.data.copy()
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
        self.sorted_data = arr
        return arr

    @measure_time
    def selection_sort(self) -> List[int]:
        """选择排序"""
        arr = self.data.copy()
        n = len(arr)
        for i in range(n):
            min_idx = i
            for j in range(i + 1, n):
                if arr[j] < arr[min_idx]:
                    min_idx = j
            arr[i], arr[min_idx] = arr[min_idx], arr[i]
        self.sorted_data = arr
        return arr

    @measure_time
    def quick_sort(self) -> List[int]:
        """快速排序"""
        arr = self.data.copy()

        def _quick_sort(lst: List[int]) -> List[int]:
            if len(lst) <= 1:
                return lst
            pivot = lst[0]
            left = [x for x in lst[1:] if x <= pivot]
            right = [x for x in lst[1:] if x > pivot]
            return _quick_sort(left) + [pivot] + _quick_sort(right)

        self.sorted_data = _quick_sort(arr)
        return self.sorted_data

    def get_sorted(self) -> List[int]:
        """ 获取排序后的数据 """
        return self.sorted_data


if __name__ == "__main__":
    data = [5, 2, 9, 1, 5, 6, 2, 9, 1, 5, 6, 2, 9, 1, 5, 6, 2, 9, 1, 5, 6]
    sorter = Sorter(data)

    print("原数据:", data)
    print("冒泡排序:", sorter.bubble_sort())
    print("选择排序:", sorter.selection_sort())
    print("快速排序:", sorter.quick_sort())
