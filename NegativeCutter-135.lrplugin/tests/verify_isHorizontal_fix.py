"""
Lua-equivalent verification: model parseJson (before/after fix) + directionAlign decision.
Uses real detect_thumb.py output for the 3 test TIFs.
"""
import json
import subprocess


def parse_json_buggy(raw):
    """Old behavior: json.decode, no isHorizontal lift."""
    return json.loads(raw)


def parse_json_fixed(raw):
    """New behavior: lift data.debug.isHorizontal -> data.isHorizontal, fallback to W>=H."""
    data = json.loads(raw)
    if data.get("isHorizontal") is None:
        if isinstance(data.get("debug", {}).get("isHorizontal"), bool):
            data["isHorizontal"] = data["debug"]["isHorizontal"]
        else:
            data["isHorizontal"] = (data.get("sourceWidth", 0) or 0) >= (
                data.get("sourceHeight", 0) or 0
            )
    return data


def will_swap(data, lr_w, lr_h):
    """Replicates directionAlign: isPyH ~= isLrH triggers swap.
       Python None != False is True (matches Lua nil ~= false)."""
    is_py = data.get("isHorizontal")  # may be None
    is_lr = lr_w >= lr_h
    return is_py != is_lr


print(f"{'TIF':14s} {'lrDim':14s} {'oldIsH':8s} {'newIsH':8s} {'oldSwap':8s} {'newSwap':8s}")
print("-" * 70)
all_old_swap = []
all_new_swap = []
for name in ["52191", "52194", "luckyc20013"]:
    out = subprocess.check_output(
        ["python3", "FilmCrop_Clean.lrplugin/detect_thumb.py",
         f"test_files/{name}.tif", "--frames", "6"],
        stderr=subprocess.DEVNULL,
    ).decode()
    raw = out.strip().split("\n")[-1]
    d_old = parse_json_buggy(raw)
    d_new = parse_json_fixed(raw)
    lr_w, lr_h = d_new["sourceWidth"], d_new["sourceHeight"]
    old_swap = will_swap(d_old, lr_w, lr_h)
    new_swap = will_swap(d_new, lr_w, lr_h)
    all_old_swap.append(old_swap)
    all_new_swap.append(new_swap)
    print(
        f"{name:14s} {lr_w}x{lr_h:<8d} "
        f"{str(d_old.get('isHorizontal')):8s} {str(d_new.get('isHorizontal')):8s} "
        f"{'YES' if old_swap else 'no':8s} {'YES' if new_swap else 'no':8s}"
    )

print()
print("Hypothetical horizontal-strip (sanity check fix is not over-correcting):")
fake = {"sourceWidth": 42000, "sourceHeight": 4700,
        "frames": [{"index": 1, "top": 0}],
        "debug": {"isHorizontal": True}}
fake_raw = json.dumps(fake)
d_old = parse_json_buggy(fake_raw)
d_new = parse_json_fixed(fake_raw)
print(f"  old isHorizontal={d_old.get('isHorizontal')}  swap={will_swap(d_old, 42000, 4700)}")
print(f"  new isHorizontal={d_new.get('isHorizontal')}  swap={will_swap(d_new, 42000, 4700)}  <- expect no")

print()
ok = all(all_old_swap) and not any(all_new_swap)
if ok:
    print("RESULT: PASS  (old: all swap [bug confirmed]  new: none swap [fix works])")
else:
    print("RESULT: FAIL")
    print(f"  old_swap = {all_old_swap}  new_swap = {all_new_swap}")
