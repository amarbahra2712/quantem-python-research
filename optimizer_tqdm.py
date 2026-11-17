# -*- coding: utf-8 -*-
"""
Created on Tue Apr 19 17:49:30 2022

@author: quant
"""

import time
from multiprocessing import Pool
import test_code_v2
from tqdm import tqdm


startTime = time.time()

def imap_unordered_bar(func, args):
    p = Pool()
    res_list = []
    with tqdm(total = len(args), position=0, leave=True) as pbar:
        for i, res in tqdm(enumerate(p.imap_unordered(func, args))):
            pbar.update()
            res_list.append(res)
    pbar.close()
    p.close()
    p.join()
    return res_list


if __name__ == '__main__':
    result = imap_unordered_bar(test_code_v2.optimize, range(54500))
   

executionTime = (time.time() - startTime)
print('Execution time in seconds: ' + str(executionTime))