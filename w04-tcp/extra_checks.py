import json
import random
import sys
from pathlib import Path

week = Path(__file__).resolve().parent
(week / 'out').mkdir(exist_ok=True)
sys.path.insert(0, str(week))
import bench
from task3_congestion import YourControl
from task1_rdt import Sender, Receiver, UnreliableChannel

results = []
for factor in (0.5, 0.6, 0.65, 0.7):
    class Variant(YourControl):
        def __init__(self):
            super().__init__()
            self.backoff = factor
    result = dict(backoff=factor, **bench.simulate(Variant))
    results.append(result)
    print(result)
(week / 'out' / 'backoff_comparison.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

# The supplied verify() recreates its RNG for every byte; exercise varied bytes too.
checks = []
for seed in range(20):
    for size in (0, 1, 7, 8, 9, 2000, 2003):
        rng = random.Random(seed)
        data = bytes(rng.getrandbits(8) for _ in range(size))
        up = UnreliableChannel(seed, loss=0.2, dup=0.3, reorder=0.8)
        down = UnreliableChannel(seed + 100, loss=0.2, dup=0.3, reorder=0.8)
        sender, receiver = Sender(up, down, data), Receiver(up, down)
        for steps in range(200000):
            alive = sender.step()
            receiver.step()
            if not alive:
                break
        else:
            raise AssertionError(('did not terminate', seed, size))
        assert receiver.data() == data, (seed, size)
        checks.append({'seed': seed, 'bytes': size, 'steps': steps + 1})
print(f'Randomized reliability checks: {len(checks)} passed (20% loss, 30% duplicates, 80% reorder)')
(week / 'out' / 'reliability_checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
