from z3 import set_param

import mt19937_cracker
import v8_cracker
import v8_cracker_int
import v8_cracker_int_legacy
import v8_cracker_legacy

set_param("timeout", 10000)
set_param("parallel.enable", True)
print("init")
