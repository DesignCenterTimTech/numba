import numpy as np
from numba import *
from numbapro.vectorize.basic import BasicVectorize

def vector_add(a, b):
    a + b

pv = BasicVectorize(vector_add)
pv.add(restype=int32, argtypes=[int32, int32])
para_ufunc = pv.build_ufunc()

a = np.arange(10, dtype=np.int32)
b = np.arange(10, dtype=np.int32)

result = para_ufunc(a, b)
print result
