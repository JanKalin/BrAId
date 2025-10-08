#!/usr/bin/env python3
# -*- coding: utf-8 -*-

### Import stuff

import argparse
import getpass
import gc
import h5py
import json
import os
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from multiprocessing import shared_memory

warnings.filterwarnings("ignore", category=DeprecationWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

SAMPLING_RATE = 512
RELEVANT_STAGE = 'final'

# ---------------- Shared Memory Helpers ----------------

# On Windows, a shared memory segment can disappear if all handles are closed.
# Keep worker-owned SharedMemory objects alive for the lifetime of each worker process.
_SHM_WORKER_REGISTRY = []  # this list exists separately in each worker process


def _create_shm_from_array(arr: np.ndarray):
    """
    Create a shared memory block containing a copy of `arr`.
    Returns (name, shape, dtype_str). Keeps the worker's handle alive in a registry,
    so the parent can open it safely on Windows.
    """
    nbytes = arr.nbytes
    shm = shared_memory.SharedMemory(create=True, size=nbytes)
    try:
        view = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
        view[:] = arr
        _SHM_WORKER_REGISTRY.append(shm)  # keep worker's handle alive
        return shm.name, arr.shape, str(arr.dtype)
    except Exception:
        # If anything goes wrong, free the block in the worker
        shm.close()
        try:
            shm.unlink()
        except FileNotFoundError:
            pass
        raise


def _read_shm_array(name: str, shape, dtype: str):
    """
    Open an existing shared memory block and view it as an ndarray (no copy).
    Caller must close() and unlink() appropriately.
    """
    shm = shared_memory.SharedMemory(name=name)
    arr = np.ndarray(shape, dtype=np.dtype(dtype), buffer=shm.buf)
    return shm, arr


# ---------------- Worker: pure compute, no disk writes ----------------

def _process_one(item, args_dict, sampling_rate, relevant_stage, src_hdf5_path):
    """
    Read from src HDF5 (read-only), resample, normalise, determine [p:q],
    adjust pulses, and return shared-memory descriptors for slices + updated item.
    """
    import numpy as np
    import h5py

    dx = args_dict["dx"]
    threshold = args_dict["threshold"]
    expand = args_dict["expand"]
    admp_only = args_dict["admp_only"]
    debug = args_dict["debug"]

    try:
        with h5py.File(src_hdf5_path, 'r') as f:
            ts = item['ts_str']
            grp = f[ts]
            dataset_names = [name for name, obj in grp.items() if isinstance(obj, h5py.Dataset)]
            if '11admp' not in dataset_names:
                return {"status": "skip_missing_11admp", "ets": item.get('ets_str', '?'), "ts": ts}

            ordered_names = ['11admp'] + [x for x in dataset_names if x != '11admp']

            p = q = None
            v = item['v']
            shm_meta = []  # list of {dataset, name, shape, dtype}

            for jdx, dataset_name in enumerate(ordered_names):
                data = grp[dataset_name][...]
                if debug:
                    _ = np.array(data)  # mirrors original code (not used further)

                if jdx == 0:
                    a_old = np.arange(len(data))
                    dx_dt = dx * sampling_rate / v
                    item['dx/dt'] = dx_dt
                    x_max = float(f"{(np.floor(v * len(data) / sampling_rate / dx) * dx):.3f}")
                    a_new = np.arange(0, x_max, dx) / v * sampling_rate

                # Resample & normalise
                data_new = np.interp(a_new, a_old, data)
                m = float(np.max(data_new)) if data_new.size else 0.0
                if m == 0.0:
                    return {"status": "no_zero", "ets": item.get('ets_str', '?'), "ts": ts}
                data_new = (data_new / m).astype(np.float32, copy=False)  # shrink memory

                if jdx == 0:
                    above = np.where(data_new > threshold)[0]
                    if len(above) == 0:
                        return {"status": "no_zero", "ets": item.get('ets_str', '?'), "ts": ts}
                    try:
                        p = np.where((data_new[:above[0]] <= 0))[0][-1] + 1
                        q = np.where((data_new[above[-1]:] <= 0))[0][0] + above[-1]
                        p = max(int(p - expand[0] / dx), 0)
                        q = min(int(q + expand[1] / dx), len(data_new))
                    except IndexError:
                        return {"status": "no_zero", "ets": item.get('ets_str', '?'), "ts": ts}

                    # Adjust pulses in-place on this task's copy
                    prev_first = item['vehicle'][relevant_stage]['axle_pulses'][0]
                    for stage in ['detected', 'weighed', 'final']:
                        item['vehicle'][stage]['axle_pulses'] = [int(x / dx_dt - p)
                                                                 for x in item['vehicle'][stage]['axle_pulses']]
                    first = item['vehicle'][relevant_stage]['axle_pulses'][0]
                    if first < 160 or first > 212:
                        return {"status": "misplaced", "ets": item.get('ets_str', '?'), "ts": ts, "first": first}
                    item['Dx'] = first - prev_first

                # Slice -> shared memory (keep handle alive in worker)
                data_slice = data_new[p:q]
                shm_name, shape, dtype = _create_shm_from_array(data_slice)
                shm_meta.append({"dataset": dataset_name, "name": shm_name, "shape": shape, "dtype": dtype})

                if jdx and admp_only:
                    break

            return {"status": "ok",
                    "ts": ts,
                    "ets": item.get('ets_str', '?'),
                    "slices_shm": shm_meta,   # tiny payload
                    "updated_item": item,
                    "first": item['vehicle'][relevant_stage]['axle_pulses'][0]}

    except MemoryError:
        # Worker ran out of memory on this item; report but keep pool alive
        return {"status": "oom", "ets": item.get('ets_str', '?'), "ts": item.get('ts_str', '?')}

    except Exception as e:
        return {"status": "error", "ets": item.get('ets_str', '?'),
                "ts": item.get('ts_str', '?'), "error": repr(e)}


# ---------------- Main ----------------

def main():
    # Parse args and do simple initialisations
    parser = argparse.ArgumentParser(description="Normalises and shifts signals",
                                     fromfile_prefix_chars='@',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
    parser.add_argument("--src-hdf5", dest="src_hdf5", help="Source signals file in the data directory",
                        default="nn_signals.hdf5")
    parser.add_argument("--src-json", dest="src_json", help="Source file vehicles in the data directory",
                        default="nn_pulses.json")
    parser.add_argument("--dst-hdf5", dest="dst_hdf5",
                        help="Destination signals file in the data directory. Use NONE to prevent writing",
                        default="nn_normalised_signals.hdf5")
    parser.add_argument("--dst-json", dest="dst_json",
                        help="Destination vehicles file in the data directory. Use NONE to prevent writing",
                        default="nn_normalised_pulses.json")

    parser.add_argument("--dx", help="Resampled data spatial resolution", type=float, default=0.05)
    parser.add_argument("--threshold", help="Threshold for search of the positive region", type=float, default=0.20)
    parser.add_argument("--expand", help="Expand positive region by this many metres to left and right",
                        type=float, nargs=2, default=[8, 8])

    grp_selection = parser.add_mutually_exclusive_group()
    grp_selection.add_argument("--ets", help="Process single vehicle")
    grp_selection.add_argument("--items", help="Process these items. Default is to process all files",
                               type=int, nargs=2)

    parser.add_argument("--plot", help="Plot overlayed 11admp signals and first --plot pulses", type=int)
    parser.add_argument("--legend", help="Add label to plot (use for small number of items", action='store_true')

    parser.add_argument("--admp-only", dest="admp_only", help="Process just the 11admp signal", action='store_true')
    parser.add_argument("--debug", help="Various debugging", action='store_true')

    parser.add_argument("--workers", type=int, help="Max worker processes (default: os.cpu_count())", default=None)
    parser.add_argument("--inflight", type=int, help="Max in-flight tasks (default: 2 * workers)", default=None)

    try:
        __IPYTHON__  # noqa
        if True and getpass.getuser() == 'jank':
            args = parser.parse_args(
                r"--plot 1 --admp-only --legend --dst-hdf5 NONE --dst-json NONE --ets 2014-03-20-06-40-36-943".split()
            )
        else:
            raise Exception
    except Exception:
        args = parser.parse_args()

    # Read the json file
    with open(os.path.join(args.data_dir, args.src_json)) as f:
        items = json.load(f)

    if args.ets:
        items = [x for x in items if x['ets_str'] == args.ets]
        if not items:
            raise ValueError(f"{args.ets} not found in {args.src_json}")

    # Plot preparation
    if args.plot:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)

    # Ensure destination HDF5 exists (if writing)
    if args.dst_hdf5 != "NONE":
        with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'w') as f:
            pass

    # Prepare outputs
    new_items = []
    no_zero = []
    misplaced = []
    ooms = []  # ETS that caused MemoryError

    # Respect --items selection
    work_items = items[args.items[0]:args.items[1]] if args.items else items

    # Map ts_str -> index in `items` so we can write back updated entries
    index_map = {it['ts_str']: idx for idx, it in enumerate(items)}

    # Pack small, picklable args for workers
    args_dict = dict(dx=args.dx, threshold=args.threshold, expand=args.expand,
                     admp_only=args.admp_only, debug=args.debug)
    src_hdf5_path = os.path.join(args.data_dir, args.src_hdf5)

    # Concurrency settings
    max_workers = args.workers or (os.cpu_count() or 1)
    max_inflight = args.inflight or (max_workers * 2)

    def plot_from_shared(res):
        if not args.plot:
            return
        # Find '11admp' slice and plot BEFORE we unlink memory
        for meta in res["slices_shm"]:
            if meta["dataset"] == "11admp":
                shm, arr = _read_shm_array(meta["name"], meta["shape"], meta["dtype"])
                try:
                    data_plot = np.array(arr, copy=True)  # small copy for plotting
                finally:
                    shm.close()  # do not unlink here; parent will unlink after writing
                if data_plot.size:
                    ax1.plot(data_plot, label=res["ets"])
                    a = np.zeros(len(data_plot), dtype=int)
                    pulses = res["updated_item"]['vehicle'][RELEVANT_STAGE]['axle_pulses'][:args.plot]
                    pulses = [p for p in pulses if 0 <= p < len(a)]
                    a[pulses] = 1
                    ax2.plot(a, label=res["ets"])
                break

    def handle_result(res):
        status = res["status"]
        if status == "ok":
            ts = res["ts"]
            shm_list = res["slices_shm"]

            # Write to HDF5 (read directly from shared memory -> HDF5)
            if args.dst_hdf5 != "NONE":
                with h5py.File(os.path.join(args.data_dir, args.dst_hdf5), 'a') as g:
                    grp = g.create_group(ts)
                    for meta in shm_list:
                        name, shape, dtype, ds = meta["name"], meta["shape"], meta["dtype"], meta["dataset"]
                        shm, arr = _read_shm_array(name, shape, dtype)
                        try:
                            grp.create_dataset(ds, data=arr, compression="gzip",
                                               compression_opts=4, shuffle=True)
                        finally:
                            # Always release the parent's handle; unlink the name
                            try:
                                shm.close()
                            finally:
                                try:
                                    shm.unlink()
                                except (FileNotFoundError, PermissionError):
                                    # If already unlinked or still in use, ignore; will be freed when worker exits
                                    pass
            else:
                # Even if not writing HDF5, we must release parent's handles if we opened any (we didn't here)

                # Optionally, if you want to aggressively free memory names anyway:
                for meta in shm_list:
                    try:
                        shm = shared_memory.SharedMemory(name=meta["name"])
                        shm.close()
                        try:
                            shm.unlink()
                        except (FileNotFoundError, PermissionError):
                            pass
                    except FileNotFoundError:
                        pass

            # Update items + stats
            idx = index_map.get(ts)
            if idx is not None:
                items[idx] = res["updated_item"]
                new_items.append(res["updated_item"])
            else:
                new_items.append(res["updated_item"])

        elif status == "no_zero":
            no_zero.append(f"{res.get('ets','?')}\t{res.get('ts','?')}")
        elif status == "misplaced":
            misplaced.append(f"{res.get('ets','?')}\t{res.get('ts','?')}\t{res.get('first','?')}")
        elif status == "oom":
            ooms.append(f"{res.get('ets','?')}\t{res.get('ts','?')}")
            print(f"Worker OOM on {res.get('ts','?')} ({res.get('ets','?')}). Skipping.")
        elif status == "error":
            print("Worker error:", res.get("error"))

    # Launch workers with bounded in-flight window and stream results
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        it = iter(work_items)
        futures = set()

        # prime the pump
        try:
            for _ in range(min(max_inflight, len(work_items))):
                item = next(it)
                futures.add(ex.submit(_process_one, item, args_dict, SAMPLING_RATE,
                                      RELEVANT_STAGE, src_hdf5_path))
        except StopIteration:
            pass

        pbar = tqdm(total=len(work_items), ncols=60, mininterval=1, ascii=True)
        while futures:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done:
                try:
                    res = fut.result()
                except MemoryError:
                    # Very rare; worker-side catch should usually handle it
                    print("Parent caught MemoryError while receiving a result; skipping one task.")
                    pbar.update(1)
                    continue

                # If plotting, do it BEFORE unlinking the shared memory
                if res.get("status") == "ok" and args.plot:
                    plot_from_shared(res)

                handle_result(res)
                pbar.update(1)

                # submit a new task to keep the inflight window constant
                try:
                    item = next(it)
                    futures.add(ex.submit(_process_one, item, args_dict, SAMPLING_RATE,
                                          RELEVANT_STAGE, src_hdf5_path))
                except StopIteration:
                    pass

        pbar.close()

    # Now write the changed JSON (items has been updated in-place)
    if args.dst_json != 'NONE':
        with open(os.path.join(args.data_dir, args.dst_json), 'w') as f:
            json.dump(items[args.items[0]:args.items[1]] if args.items else new_items, f, indent=2)

    # Dump logs
    if no_zero:
        print(f"There were {len(no_zero)} files where zero could not be found.")
        with open("no_zero.log", 'w') as f:
            f.writelines("\n".join(no_zero))

    if misplaced:
        print(f"There were {len(misplaced)} files where pulse was misplaced.")
        with open("misplaced.log", 'w') as f:
            f.writelines("\n".join(misplaced))

    if ooms:
        print(f"There were {len(ooms)} files that caused MemoryError.")
        with open("oom.log", 'w') as f:
            f.writelines("\n".join(ooms))

    # Calculate stats for the first pulse
    if new_items:
        firsts = [x['vehicle'][RELEVANT_STAGE]['axle_pulses'][0] for x in new_items]
        print(f"First pulse positions are {np.mean(firsts)} \u00B1 {np.std(firsts):.1f}, "
              f"min: {np.min(firsts)}, max: {np.max(firsts)}")

        # Show plots
        if args.plot:
            if args.legend:
                ax1.legend()
                ax2.legend()
            plt.tight_layout()
            plt.show()
    else:
        print("No output items")


if __name__ == "__main__":
    main()
