"""Check that the level 6 redesign preserves legacy geometry and observation-only physics."""
import argparse
from pathlib import Path

import numpy as np

from laser.env import DEFAULT_BUILD, LaserEnv, N_ACTIONS


def compare(level, builds, designs, observation, worker, rng, *, campaign_layouts=True, reference_observation=1):
    env_args = dict(n_areas=8, seed=716 + level, level=level, campaign_layouts=campaign_layouts)
    reference = LaserEnv(**env_args, worker_id=worker, build=builds[0], level6_design=designs[0],
                         obs_mode=reference_observation)
    try:
        candidate = LaserEnv(**env_args, worker_id=worker + 1, build=builds[1], level6_design=designs[1],
                             obs_mode=observation)
        try:
            fields = 66 if observation == reference_observation else 11
            first = reference.reset(expected_level=level)
            second = candidate.reset(expected_level=level)
            np.testing.assert_array_equal(first[:, :fields], second[:, :fields])
            if observation == 2:
                gates = second[:, 11:].reshape(candidate.n, 5, 11)
                assert np.any(np.all(gates[:, :, :4] == [1, 1, 0, 0], axis=2))
            for _ in range(160):
                actions = rng.integers(N_ACTIONS, size=candidate.n)
                first, second = reference.step(actions), candidate.step(actions)
                for field in ("obs", "final_obs"):
                    np.testing.assert_array_equal(first[field][:, :fields], second[field][:, :fields])
                for field in ("reward", "terminated", "truncated"):
                    np.testing.assert_array_equal(first[field], second[field])
                assert first["results"] == second["results"]
        finally:
            candidate.close()
    finally:
        reference.close()


def compare_with_safety(build, horizon, worker, rng):
    options = dict(n_areas=8, seed=942, level=6, build=build, level6_design=2)
    control = LaserEnv(**options, worker_id=worker)
    try:
        stage6_override = {"stage6_safety_horizon": horizon} if horizon > 2 else {}
        masked = LaserEnv(**options, worker_id=worker + 1, level6_safety_steps=min(horizon, 2), **stage6_override)
        try:
            np.testing.assert_array_equal(control.reset(), masked.reset())
            checked = 0
            for _ in range(200):
                actions = rng.choice((4, 7, 8, 16, 25), size=masked.n)
                mask = masked.action_mask
                constrained = np.zeros(masked.n, dtype=bool) if mask is None else mask.any(axis=1)
                for slot in np.flatnonzero(constrained):
                    actions[slot] = rng.choice(np.flatnonzero(~mask[slot]))
                first, second = control.step(actions), masked.step(actions)
                for field in ("obs", "final_obs", "reward", "terminated", "truncated"):
                    np.testing.assert_array_equal(first[field], second[field])
                assert first["results"] == second["results"]
                assert not any(constrained[slot] and outcome == "hit" for slot, outcome, _ in second["results"])
                checked += int(constrained.sum())
            assert checked > 0, "The Unity build did not return a collision mask"
            print(f"Verified {checked} constrained decisions with horizon {horizon}.")
        finally:
            masked.close()
    finally:
        control.close()


def check_paired_layouts(build, worker):
    env = LaserEnv(n_areas=8, seed=942, level=6, build=build, worker_id=worker, level6_design=2)
    try:
        batch_starts = []
        for batch in (2000, 2001, 2000):
            env.set_param("evaluation_layout_batch", batch)
            obs, warmup = env.evaluation_reset(6)
            starts = obs.copy()
            actions = np.full(env.n, 7)
            for _ in range(201):
                if not warmup.any():
                    break
                preparing = warmup.copy()
                obs = env.evaluation_step(actions, warmup)["obs"]
                starts[preparing & ~warmup] = obs[preparing & ~warmup]
            assert not warmup.any()
            batch_starts.append(starts)
            # Advance the RNG independently in every room before requesting another batch.
            for _ in range(230):
                env.step(actions)
        np.testing.assert_array_equal(batch_starts[0], batch_starts[2])
        assert np.all(np.any(batch_starts[0] != batch_starts[1], axis=1))
        print("Verified fresh layouts repeat only for the same evaluation batch.")
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default=DEFAULT_BUILD, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--worker", default=2700, type=int)
    parser.add_argument("--check-safety", action="store_true")
    parser.add_argument("--check-paired-layouts", action="store_true")
    parser.add_argument("--safety-horizons", type=int, choices=(1, 2, 3), nargs="+", default=(1, 2))
    parser.add_argument("--all-stages", action="store_true", help="compare equivalent builds in all observation modes")
    args = parser.parse_args()
    rng = np.random.default_rng(716)
    if args.all_stages:
        builds = (args.reference, args.candidate)
        for level in range(1, 11):
            for fixed in (False, True):
                compare(level, builds, (2, 2), 1, args.worker, rng, campaign_layouts=fixed)
        for obs_mode in (0, 2):
            compare(6, builds, (2, 2), obs_mode, args.worker, rng, reference_observation=obs_mode)
        print("Verified 28,160 transitions across all stages, layouts and observation modes.")
    else:
        for level in (5, 6, 7):
            compare(level, (args.reference, args.candidate), (0, 0), 1, args.worker, rng)
        builds = (args.candidate, args.candidate)
        for level in (5, 7):
            compare(level, builds, (0, 2), 1, args.worker, rng)
        compare(6, builds, (2, 2), 2, args.worker, rng)
        print("Verified 7,680 transitions against legacy and observation-only controls.")
    if args.check_safety:
        for horizon in args.safety_horizons:
            compare_with_safety(args.candidate, horizon, args.worker, rng)
    if args.check_paired_layouts:
        check_paired_layouts(args.candidate, args.worker)


if __name__ == "__main__":
    main()
