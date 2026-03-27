#!/home/chenmu/.conda/envs/python/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import warnings
import argparse
import numpy as np

from pymatgen.core import Structure

# -----------------------------
# Try importing IDPPSolver (new/old pymatgen diffusion packages)
# -----------------------------
try:
    from pymatgen.analysis.diffusion.neb.pathfinder import IDPPSolver
    _IDPP_SRC = "pymatgen-analysis-diffusion"
except ImportError:
    try:
        from pymatgen_diffusion.neb.pathfinder import IDPPSolver
        _IDPP_SRC = "pymatgen-diffusion"
    except ImportError:
        print("ERROR: Neither new nor old version of pymatgen diffusion IDPP solver found.")
        print("Please install via one of the following:")
        print("  pip install pymatgen-analysis-diffusion")
        print("  conda install -c conda-forge pymatgen-analysis-diffusion")
        sys.exit(1)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="IDPP interpolation for NEB initial guess + optional visualization export (shift/repeat)."
    )
    # Backward compatible positional args
    p.add_argument("init_poscar", help="Initial POSCAR/CONTCAR file")
    p.add_argument("final_poscar", help="Final POSCAR/CONTCAR file")
    p.add_argument("nimages", type=int, help="Number of intermediate images (typical VTST convention)")

    # IDPP knobs (keep your defaults)
    p.add_argument("--sort_tol", type=float, default=1.0, help="IDPP sort tolerance (default 1.0)")
    p.add_argument("--maxiter", type=int, default=5000, help="Max iterations (default 5000)")
    p.add_argument("--tol", type=float, default=1e-5, help="Energy tolerance (default 1e-5)")
    p.add_argument("--gtol", type=float, default=1e-3, help="Force tolerance (default 1e-3)")
    p.add_argument("--step_size", type=float, default=0.05, help="Step size (default 0.05)")
    p.add_argument("--max_disp", type=float, default=0.05, help="Max displacement (default 0.05)")
    p.add_argument("--spring_const", type=float, default=5.0, help="Spring constant (default 5.0)")

    # Output control
    p.add_argument("--quiet", action="store_true", help="Suppress most prints during IDPP run")
    p.add_argument("--no_default_xyz", action="store_true",
                   help="Do not write the legacy neb_guess.xyz output")

    # Visualization export (does NOT modify the saved POSCARs)
    p.add_argument("--shift", nargs=3, type=float, default=None,
                   metavar=("DX", "DY", "DZ"),
                   help="Fractional shift for visualization (dx dy dz), wrapped into [0,1)")
    p.add_argument("--repeat", nargs=3, type=int, default=None,
                   metavar=("A", "B", "C"),
                   help="Supercell repeat for visualization (a b c), e.g. 2 2 1")
    p.add_argument("--anim", type=str, default=None,
                   help="Animation output filename (e.g. neb_shift_2x2x1.extxyz)")
    p.add_argument("--animfmt", type=str, default="extxyz",
                   help="Animation output format: extxyz / xyz / traj ... (default extxyz)")

    return p.parse_args(argv)


def _shift_atoms_fractional_ase(atoms, shift_vec):
    """Shift ASE Atoms by fractional vector and wrap into cell."""
    shift_vec = np.array(shift_vec, dtype=float)
    sp = atoms.get_scaled_positions()
    sp = (sp + shift_vec) % 1.0
    atoms.set_scaled_positions(sp)
    atoms.wrap()
    return atoms


def export_legacy_xyz_from_poscars(n_frames, out_name="neb_guess.xyz"):
    """Legacy behavior: export frames from 00/..../POSCAR to a plain xyz (via ASE if available)."""
    try:
        from ase.io import read, write
    except ImportError:
        # fallback: pymatgen XYZ (no cell info)
        from pymatgen.io.xyz import XYZ
        with open(out_name, "w") as f:
            for i in range(n_frames):
                s = Structure.from_file(f"{i:02d}/POSCAR", primitive=False)
                f.write(str(XYZ(s)) + "\n")
        return False

    images = [read(f"{i:02d}/POSCAR") for i in range(n_frames)]
    write(out_name, images, format="xyz")
    return True


def export_animation_from_poscars(
    n_frames,
    shift=None,
    repeat=None,
    out="neb_guess_shifted.extxyz",
    out_format="extxyz"
):
    """
    Export visualization trajectory from saved POSCARs WITHOUT modifying them.
    Requires ASE if shift/repeat or extxyz is desired.
    """
    try:
        from ase.io import read, write
    except ImportError:
        raise RuntimeError(
            "ASE is required for --shift / --repeat / extxyz export.\n"
            "Please install ASE, e.g.:\n"
            "  pip install ase\n"
            "or\n"
            "  conda install -c conda-forge ase"
        )

    images = []
    for i in range(n_frames):
        a = read(f"{i:02d}/POSCAR")
        a.wrap()

        if shift is not None:
            a = _shift_atoms_fractional_ase(a, shift)

        if repeat is not None:
            a = a.repeat(tuple(repeat))

        images.append(a)

    write(out, images, format=out_format)


def main():
    args = parse_args(sys.argv[1:])

    # Silence warnings (but not stdout)
    warnings.filterwarnings("ignore")

    if not args.quiet:
        print(f"Using IDPP solver from: {_IDPP_SRC}")

    # Optional: quiet mode suppresses prints during solver run
    if args.quiet:
        _old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
    else:
        _old_stdout = None

    # Load endpoints
    # Keep your original behavior: Structure.from_file(file, False)
    init_struct = Structure.from_file(args.init_poscar, primitive=False)
    final_struct = Structure.from_file(args.final_poscar, primitive=False)

    # Run IDPP
    obj = IDPPSolver.from_endpoints(
        endpoints=[init_struct, final_struct],
        nimages=args.nimages,
        sort_tol=args.sort_tol
    )

    new_path = obj.run(
        maxiter=args.maxiter,
        tol=args.tol,
        gtol=args.gtol,
        step_size=args.step_size,
        max_disp=args.max_disp,
        spring_const=args.spring_const
    )

    # Restore stdout if quiet
    if args.quiet:
        sys.stdout.close()
        sys.stdout = _old_stdout

    # Write POSCARs to 00/01/...
    for i, s in enumerate(new_path):
        image_dir = f"{i:02d}"
        os.makedirs(image_dir, exist_ok=True)
        s.to(fmt="poscar", filename=os.path.join(image_dir, "POSCAR"))

    n_frames = len(new_path)

    if not args.quiet:
        print(f"[?] IDPP path generated. Frames written: {n_frames}  (dirs: 00 .. {n_frames-1:02d})")

    # Legacy xyz output (same filename as your original script)
    if not args.no_default_xyz:
        used_ase = export_legacy_xyz_from_poscars(n_frames, out_name="neb_guess.xyz")
        if not args.quiet:
            if used_ase:
                print("[?] Legacy trajectory written: neb_guess.xyz (ASE)")
            else:
                print("[?] Legacy trajectory written: neb_guess.xyz (pymatgen XYZ fallback)")

    # New visualization export (shift/repeat + extxyz recommended)
    if (args.anim is not None) or (args.shift is not None) or (args.repeat is not None):
        out_name = args.anim or "neb_guess_shifted.extxyz"
        export_animation_from_poscars(
            n_frames=n_frames,
            shift=args.shift,
            repeat=args.repeat,
            out=out_name,
            out_format=args.animfmt
        )
        if not args.quiet:
            print(f"[?] Visualization trajectory written: {out_name} (format={args.animfmt})")
            if args.shift is not None:
                print(f"    shift(frac) = {args.shift}")
            if args.repeat is not None:
                print(f"    repeat      = {args.repeat}")

    if not args.quiet:
        print("Improved interpolation of NEB initial guess has been generated. BYE.")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemError("Syntax Error! Run as: python idpp_v2.py ini/POSCAR fin/POSCAR 8")
    main()
