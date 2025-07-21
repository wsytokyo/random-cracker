from z3 import LShR, set_param

from random_cracker import RandomCracker, RngType
from v8_cracker import DivisionConverter, V8Cracker


class V8IntConverter(DivisionConverter):
    def __init__(self, multiplier: int):
        self._multiplier = multiplier

    def to_value(self, state: int) -> int:
        return int(super().to_value(state) * self._multiplier)

    def from_value(self, int_value: int) -> int:
        return super().from_value(int_value / self._multiplier)


class V8IntCracker(V8Cracker):

    rng_type = RngType.V8_INT

    def __init__(self, multiplier: int):
        set_param("timeout", 10000)
        super().__init__()
        self._multiplier = multiplier
        self.converter = V8IntConverter(multiplier)

    def _add_constraint(self, new_val: int):
        shift = self.converter.get_ignored_lower_bits()
        known_bits_lower = self.converter.from_value(new_val)
        known_bits_upper = self.converter.from_value(new_val + 1)
        i = shift
        while known_bits_lower >> i != known_bits_upper >> i:
            i += 1
        self._solver.add(LShR(self._s0_sym, i) == known_bits_lower >> i)
        self._rotate_symbolic_state()


if __name__ == "__main__":
    multiplier = 2**32

    cracker = RandomCracker.create(RngType.V8_INT, multiplier=multiplier)
    seq = [
        0.14125615467524433,
        0.26338755919900825,
        0.35195985313880274,
        0.017540229969875143,
        0.9709689202550907,
        0.6878379941821865,
        0.26971805726378495,
        0.7918168602898303,
        0.870242991224168,
        0.7266674854224073,
        0.02669613161449602,
        0.7837415283729079,
        0.3205086721472562,
        0.5516568532161495,
        0.21067570655396728,
        0.4171358133289702,
        0.5267603220387562,
        0.19739876622115204,
        0.5044790755285522,
        0.7527406751741436,
    ]
    observed_sequence = seq[:16]
    expected_predictions = seq[16:]
    observed_sequence_int = [int(val * multiplier) for val in observed_sequence]
    expected_predictions_int = [int(val * multiplier) for val in expected_predictions]
    for val in observed_sequence_int:
        cracker.add_value(val)
        print(cracker.status.name)
    for i in range(len(expected_predictions_int)):
        print(cracker.predict_next(), expected_predictions_int[i])
