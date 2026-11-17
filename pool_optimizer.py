# -*- coding: utf-8 -*-
"""
Created on Mon Apr 18 09:51:11 2022

@author: quant
"""

import time
from multiprocessing import Pool
import test_code_v2

startTime = time.time()

#def log_results(result):
#    global result_list
#    result_list.append(result)
   
if __name__ == '__main__':
    numbers = range(10)
    p = Pool()
    result = p.map_async(test_code_v2.optimize, numbers)
#    tf_arr = result
    
    p.close()
    p.join()
    result = result.get()

executionTime = (time.time() - startTime)
print('Execution time in seconds: ' + str(executionTime))

