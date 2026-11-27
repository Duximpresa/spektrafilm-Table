"""Compare the production CPU/CUDA backends using a decoded image and GUI state.

Example (from the repository root):
  python scripts/benchmark_execution.py --image decoded.npy --state state.json --output new-run
Output must be a new directory. Private inputs/outputs should not be committed.
"""

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

import numba
import numpy as np
from numba import njit, prange

from spektrafilm.runtime.execution import ExecutionOptions
from spektrafilm.runtime.params_builder import digest_params
from spektrafilm.runtime.process import Simulator
from spektrafilm_gui.params_mapper import build_params_from_state
from spektrafilm_gui.persistence import gui_state_from_dict


@njit(parallel=True)
def seed_threads(seed):
    for _ in prange(numba.get_num_threads()):
        np.random.seed(seed + numba.get_thread_id())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repeat", type=int, default=4, help="includes first/cold process call"
    )
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    image = np.load(args.image)
    state = gui_state_from_dict(json.loads(args.state.read_text(encoding="utf-8")))
    params = build_params_from_state(state)
    params.settings.preview_mode = False
    params = digest_params(params)
    rows = []
    for mode in ("cpu", "cuda"):
        sim = Simulator(
            params, execution=ExecutionOptions(backend=mode, allow_fallback=False)
        )
        try:
            for run in range(args.repeat):
                seed_threads(12345)
                np.random.seed(12345)
                started = perf_counter()
                result = sim.process(
                    image,
                    on_progress=lambda stage, done, total, mode=mode, run=run: print(
                        mode, run, stage, done, total, flush=True
                    ),
                )
                row = {
                    "backend": mode,
                    "run": run,
                    "seconds": perf_counter() - started,
                    "status": sim.execution_status(),
                    "timings": dict(sim.get_timings()),
                    "finite": bool(np.isfinite(result).all()),
                    "shape": list(result.shape),
                    "numba_threads": numba.get_num_threads(),
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
                (args.output / "timings.json").write_text(
                    json.dumps(rows, indent=2), encoding="utf-8"
                )
                if run == args.repeat - 1:
                    np.save(args.output / f"{mode}.npy", result)
                del result
        finally:
            sim.close()
    reference = np.load(args.output / "cpu.npy", mmap_mode="r")
    actual = np.load(args.output / "cuda.npy", mmap_mode="r")
    maximum, sum_squares, count = 0.0, 0.0, 0
    for start in range(0, len(reference), 64):
        diff = actual[start : start + 64] - reference[start : start + 64]
        maximum = max(maximum, float(np.max(np.abs(diff))))
        sum_squares += float(np.sum(diff**2))
        count += diff.size
    accuracy = {
        "max_absolute_error": maximum,
        "rmse": (sum_squares / count) ** 0.5,
        "threads": numba.get_num_threads(),
        "seed": 12345,
        "cpu_env": {
            key: os.environ.get(key)
            for key in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
    }
    (args.output / "accuracy.json").write_text(
        json.dumps(accuracy, indent=2), encoding="utf-8"
    )
    print(json.dumps(accuracy), flush=True)
    if not all(row["finite"] for row in rows) or maximum > 1e-9:
        raise RuntimeError(
            "Numerical regression: investigate before accepting the result"
        )


if __name__ == "__main__":
    main()
