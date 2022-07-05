import numpy as np
from numba.cuda.testing import (unittest, CUDATestCase, skip_unless_cc_53,
                                skip_on_cudasim)
from numba import cuda
from numba.core.types import f2,b1
import operator
from numba.cuda import compile_ptx
import itertools
from numba.np.numpy_support import from_dtype


def simple_fp16_gt(ary, a, b):
    ary[0] = a > b


def simple_fp16_ge(ary, a, b):
    ary[0] = a >= b


def simple_fp16_lt(ary, a, b):
    ary[0] = a < b


def simple_fp16_le(ary, a, b):
    ary[0] = a <= b


def simple_fp16_eq(ary, a, b):
    ary[0] = a == b


def simple_fp16_ne(ary, a, b):
    ary[0] = a != b


@cuda.jit('b1(f2, f2)', device=True)
def hlt_func_1(x, y):
    return x < y


@cuda.jit('b1(f2, f2)', device=True)
def hlt_func_2(x, y):
    return x < y


def test_multiple_hcmp_1(r, a, b, c):
    # float16 predicates used in two separate functions
    r[0] = hlt_func_1(a, b) and hlt_func_2(b, c)


def test_multiple_hcmp_2(r, a, b, c):
    # The same float16 predicate used in the caller and callee
    r[0] = hlt_func_1(a, b) and b < c


def test_multiple_hcmp_3(r, a, b, c):
    # Different float16 predicates used in the caller and callee
    r[0] = hlt_func_1(a, b) and c >= b


def test_multiple_hcmp_4(r, a, b, c):
    # The same float16 predicates used twice in a function
    r[0] = a < b and b < c


def test_multiple_hcmp_5(r, a, b, c):
    # Different float16 predicates used in a function
    r[0] = a < b and c >= b


class TestOperatorModule(CUDATestCase):
    def setUp(self):
        super().setUp()
        np.random.seed(0)

    """
    Test if operator module is supported by the CUDA target.
    """
    def operator_template(self, op):
        @cuda.jit
        def foo(a, b):
            i = 0
            a[i] = op(a[i], b[i])

        a = np.ones(1)
        b = np.ones(1)
        res = a.copy()
        foo[1, 1](res, b)

        np.testing.assert_equal(res, op(a, b))

    def test_add(self):
        self.operator_template(operator.add)

    def test_sub(self):
        self.operator_template(operator.sub)

    def test_mul(self):
        self.operator_template(operator.mul)

    def test_truediv(self):
        self.operator_template(operator.truediv)

    def test_floordiv(self):
        self.operator_template(operator.floordiv)

    @skip_unless_cc_53
    def test_fp16_comparison(self):
        functions = (simple_fp16_gt, simple_fp16_ge,
                     simple_fp16_lt, simple_fp16_le,
                     simple_fp16_eq, simple_fp16_ne)
        ops = (operator.gt, operator.ge, operator.lt, operator.le,
               operator.eq, operator.ne)

        for fn, op in zip(functions, ops):
            with self.subTest(op=op):
                kernel = cuda.jit("void(b1[:], f2, f2)")(fn)

                got = np.zeros(1, dtype=np.bool8)
                arg1 = np.random.random(1).astype(np.float16)
                arg2 = np.random.random(1).astype(np.float16)

                kernel[1, 1](got, arg1[0], arg2[0])
                expected = op(arg1, arg2)
                self.assertEqual(got[0], expected)

    @skip_unless_cc_53
    def test_mixed_fp16_comparison(self):
        functions = (simple_fp16_gt, simple_fp16_ge,
                     simple_fp16_lt, simple_fp16_le,
                     simple_fp16_eq, simple_fp16_ne)
        ops = (operator.gt, operator.ge, operator.lt, operator.le,
               operator.eq, operator.ne)
        types = (np.int8, np.int16, np.int32, np.int64,
                 np.float32, np.float64)

        for (fn, op), ty in itertools.product(zip(functions, ops),
                                              types):
            with self.subTest(op=op, ty=ty):
                kernel = cuda.jit(fn)

                got = np.zeros(1, dtype=np.bool8)
                arg1 = np.random.random(1).astype(np.float16)
                arg2 = (np.random.random(1) * 100).astype(ty)

                kernel[1, 1](got, arg1[0], arg2[0])
                expected = op(arg1, arg2)
                self.assertEqual(got[0], expected)

    @skip_unless_cc_53
    def test_multiple_float16_comparisons(self):
        functions = (test_multiple_hcmp_1,
                     test_multiple_hcmp_2,
                     test_multiple_hcmp_3,
                     test_multiple_hcmp_4,
                     test_multiple_hcmp_5)
        for fn in functions:
            with self.subTest(fn=fn):
                compiled = cuda.jit("void(b1[:], f2, f2, f2)")(fn)
                ary = np.zeros(1, dtype=np.bool8)
                arg1 = np.float16(2.)
                arg2 = np.float16(3.)
                arg3 = np.float16(4.)
                compiled[1, 1](ary, arg1, arg2, arg3)
                self.assertTrue(ary[0])

    @skip_on_cudasim('Compilation unsupported in the simulator')
    def test_fp16_comparison_ptx(self):
        functions = (simple_fp16_gt, simple_fp16_ge,
                     simple_fp16_lt, simple_fp16_le,
                     simple_fp16_eq, simple_fp16_ne)
        ops = (operator.gt, operator.ge, operator.lt, operator.le,
               operator.eq, operator.ne)
        opstring = ('setp.gt.f16', 'setp.ge.f16',
                    'setp.lt.f16', 'setp.le.f16',
                    'setp.eq.f16', 'setp.ne.f16')
        args = (b1[:], f2, f2)

        for fn, op, s in zip(functions, ops, opstring):
            with self.subTest(op=op):
                ptx, _ = compile_ptx(fn, args, cc=(5, 3))
                self.assertIn(s, ptx)

    @skip_on_cudasim('Compilation unsupported in the simulator')
    def test_fp16_int8_comparison_ptx(self):
        functions = (simple_fp16_gt, simple_fp16_ge,
                     simple_fp16_lt, simple_fp16_le,
                     simple_fp16_eq, simple_fp16_ne)
        ops = (operator.gt, operator.ge, operator.lt, operator.le,
               operator.eq, operator.ne)
        types_convert = (np.int8,)

        opstring = {operator.gt:'setp.gt.f16',
                    operator.ge:'setp.ge.f16',
                    operator.lt:'setp.lt.f16',
                    operator.le:'setp.le.f16',
                    operator.eq:'setp.eq.f16',
                    operator.ne:'setp.ne.f16'}
        for (fn, op), ty in itertools.product(zip(functions, ops),
                                              types_convert):
            with self.subTest(op=op, ty=ty):
                args = (b1[:], f2, from_dtype(ty))
                ptx, _ = compile_ptx(fn, args, cc=(5, 3))
                self.assertIn(opstring[op], ptx)

    @skip_on_cudasim('Compilation unsupported in the simulator')
    def test_mixed_fp16_comparison_promotion_ptx(self):
        functions = (simple_fp16_gt, simple_fp16_ge,
                     simple_fp16_lt, simple_fp16_le,
                     simple_fp16_eq, simple_fp16_ne)
        ops = (operator.gt, operator.ge, operator.lt, operator.le,
               operator.eq, operator.ne)

        types_promote = (np.int16, np.int32, np.int64,
                         np.float32, np.float64)
        opstring = {operator.gt:'setp.gt.',
                    operator.ge:'setp.ge.',
                    operator.lt:'setp.lt.',
                    operator.le:'setp.le.',
                    operator.eq:'setp.eq.',
                    operator.ne:'setp.neu.'}
        opsuffix = {np.dtype('int32'): 'f64',
                    np.dtype('int64'): 'f64',
                    np.dtype('float32'): 'f32',
                    np.dtype('float64'): 'f64'}

        for (fn, op), ty in itertools.product(zip(functions, ops),
                                              types_promote):
            with self.subTest(op=op, ty=ty):
                arg2_ty = np.result_type(np.float16, ty)
                args = (b1[:], f2, from_dtype(arg2_ty))
                ptx, _ = compile_ptx(fn, args, cc=(5, 3))

                ops = opstring[op] + opsuffix[arg2_ty]
                self.assertIn(ops, ptx)


if __name__ == '__main__':
    unittest.main()
