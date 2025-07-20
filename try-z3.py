from z3 import *

# from z3.z3types import _coerce_exprs


class MyBitVecRef(BitVecRef):
    def __init__(self, ref, ctx):
        super().__init__(ref, ctx)

    def __rshift__(self, other):
        if isinstance(other, int):
            other = self.sort().cast(other)
        return MyBitVecRef(
            Z3_mk_bvlshr(self.ctx_ref(), self.as_ast(), other.as_ast()), self.ctx
        )


def _get_ctx(ctx) -> Context:
    if ctx is None:
        return main_ctx()
    else:
        return ctx


def MyBitVec(name, bv, ctx=None):
    ctx = _get_ctx(ctx)
    bv = BitVecSort(bv, ctx)
    return MyBitVecRef(Z3_mk_const(ctx.ref(), to_symbol(name, ctx), bv.ast), ctx)


if __name__ == "__main__":
    s = Solver()
    x = MyBitVec("x", 64)
    y = MyBitVec("y", 64)
    z = MyBitVec("z", 64)

    s.add(x == 10)
    s.add(y == 1)
    s.add(x >> y == z)

    print(s.check())
    print(s.model())
