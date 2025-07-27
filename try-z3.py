from z3 import *

x = BitVec("x", 8)
y = BitVec("y", 8)

s = Solver()
s.add(x >= -1)
s.add(x <= 0)
s.add(x != 0)
s.add(x != -1)

print(s.check())
print(s.model())
