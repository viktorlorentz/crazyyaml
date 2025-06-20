import numpy as np
from ruamel.yaml import YAML
from crazyyaml import yaml_to_crazy, crazy_to_yaml
from testdata import generate_data

yaml = YAML()

def test_compression_report(tmp_path):
    """Report compression and precision loss for various dtypes."""
    dtypes = ["float16", "float32", "float64"]
    # Generate large test data
    data = generate_data(10000)
    # Write normal YAML
    input_yaml = tmp_path / "big.yaml"
    with open(input_yaml, 'w') as f:
        yaml.dump(data, f)
    orig_size = input_yaml.stat().st_size

    results = []  # collect metrics
    for dt in dtypes:
        try:
            dtype = np.dtype(dt)
        except TypeError:
            continue

        crazy_yaml = tmp_path / f"big_{dt}.crazy.yaml"
        # Compress
        yaml_to_crazy(str(input_yaml), str(crazy_yaml), threshold=10, dtype=dtype)
        comp_size = crazy_yaml.stat().st_size
        ratio = comp_size / orig_size

        # Decompress
        out_yaml = tmp_path / f"big_{dt}_out.yaml"
        crazy_to_yaml(str(crazy_yaml), str(out_yaml))
        with open(out_yaml) as f:
            data_out = yaml.load(f)

        # Compute precision loss on 'states'
        orig_states = np.array(data['result'][0]['states'], dtype=float)
        loaded_states = np.array(data_out['result'][0]['states'], dtype=float)
        err = np.abs(orig_states - loaded_states)
        max_err = err.max()
        rel_err = err / np.maximum(np.abs(orig_states), 1e-8)
        max_rel = rel_err.max()

        # accumulate
        results.append({
            "dtype": dt,
            "orig": orig_size,
            "comp": comp_size,
            "ratio": ratio,
            "max_abs_err": max_err,
            "max_rel_err": max_rel
        })

    # print markdown table
    headers = ["dtype", "orig", "comp", "ratio", "max_abs_err", "max_rel_err"]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(":---" if h=="dtype" else "---:" for h in headers) + " |"
    print("\n" + header_line)
    print(sep_line)
    for r in results:
        print(f"| {r['dtype']} | {r['orig']} | {r['comp']} | {r['ratio']:.3f} | {r['max_abs_err']:.3e} | {r['max_rel_err']:.3e} |")

    # validate against known benchmarks
    benchmarks = {
        "float16": {"ratio": 0.097, "max_abs_err": 2.441e-4, "max_rel_err": 9.986e-4},
        "float32": {"ratio": 0.202, "max_abs_err": 2.980e-8, "max_rel_err": 5.944e-8},
        "float64": {"ratio": 0.425, "max_abs_err": 0.0,     "max_rel_err": 0.0},
    }
    margin = 0.10  # allow 10% above each benchmark

    for r in results:
        b = benchmarks[r["dtype"]]
        allowed_ratio     = b["ratio"]     * (1 + margin)
        allowed_abs_err   = b["max_abs_err"] * (1 + margin)
        allowed_rel_err   = b["max_rel_err"] * (1 + margin)

        assert r["ratio"]       <= allowed_ratio,   f"{r['dtype']} ratio too high: {r['ratio']:.3f} > {allowed_ratio:.3f}"
        assert r["max_abs_err"] <= allowed_abs_err, f"{r['dtype']} abs_err too large: {r['max_abs_err']:.3e} > {allowed_abs_err:.3e}"
        assert r["max_rel_err"] <= allowed_rel_err, f"{r['dtype']} rel_err too large: {r['max_rel_err']:.3e} > {allowed_rel_err:.3e}"

    # always pass
    assert True
