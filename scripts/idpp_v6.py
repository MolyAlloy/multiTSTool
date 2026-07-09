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
    p.add_argument("cp2k", nargs="?", default=None,
                   help="Optional final positional flag: use 'cp2k' to write ts-1.xyz ... ts-n.xyz without image folders")

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

    # CP2K output control
    p.add_argument("--cp2k_outdir", type=str, default=".",
                   help="Output directory for CP2K xyz files in cp2k mode (default: current directory)")
    p.add_argument("--no_cp2k_endpoints", action="store_true",
                   help="In cp2k mode, do not write reordered endpoint xyz files")
    p.add_argument("--cp2k_init_name", type=str, default="ts-ini.xyz",
                   help="Filename for the reordered initial endpoint in cp2k mode (default: ts-ini.xyz)")
    p.add_argument("--cp2k_final_name", type=str, default="ts-fin.xyz",
                   help="Filename for the reordered final endpoint in cp2k mode (default: fin.xyz)")
    p.add_argument("--cp2k_ts_prefix", type=str, default="ts",
                   help="Prefix for intermediate CP2K xyz images in cp2k mode (default: ts -> ts-1.xyz)")

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

    args = p.parse_args(argv)
    if args.cp2k is not None and args.cp2k.lower() != "cp2k":
        p.error("optional final positional argument must be 'cp2k'")
    args.cp2k = args.cp2k is not None
    return args


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


def write_xyz_from_structure(structure, filename):
    """Write a plain XYZ directly from a pymatgen Structure using Cartesian coordinates."""
    with open(filename, "w") as f:
        f.write(f"{len(structure)}\n")
        f.write(f"{filename}\n")
        for site in structure:
            x, y, z = site.coords
            f.write(f"{site.specie.symbol} {x:.16f} {y:.16f} {z:.16f}\n")


def write_cp2k_xyz_images(
    structures,
    outdir=".",
    include_endpoints=True,
    init_name="ts-ini.xyz",
    final_name="fin.xyz",
    ts_prefix="ts",
):
    """
    Write CP2K BAND xyz files from one internally consistent IDPP path.

    Default CP2K filenames are:
      ts-ini.xyz, ts-1.xyz ... ts-N.xyz, fin.xyz

    Rationale:
    - ts-ini.xyz is not the raw CP2K-optimized endpoint. It is frame 0 of the
      internally reordered IDPP path, using the exact same atom/site order as
      the intermediate images.
    - This naming avoids confusing the reordered endpoint with an original
      CP2K-exported ini.xyz/cif-derived structure.
    """
    os.makedirs(outdir, exist_ok=True)

    written = []
    if include_endpoints:
        init_path = os.path.join(outdir, init_name)
        write_xyz_from_structure(structures[0], init_path)
        written.append(init_path)

    for i, structure in enumerate(structures[1:-1], start=1):
        ts_path = os.path.join(outdir, f"{ts_prefix}-{i}.xyz")
        write_xyz_from_structure(structure, ts_path)
        written.append(ts_path)

    if include_endpoints:
        final_path = os.path.join(outdir, final_name)
        write_xyz_from_structure(structures[-1], final_path)
        written.append(final_path)

    return written


def export_legacy_xyz_from_structures(structures, out_name="neb_guess.xyz"):
    """Export a multi-frame plain XYZ directly from pymatgen Structures."""
    with open(out_name, "w") as f:
        for iframe, structure in enumerate(structures):
            f.write(f"{len(structure)}\n")
            f.write(f"frame {iframe}\n")
            for site in structure:
                x, y, z = site.coords
                f.write(f"{site.specie.symbol} {x:.16f} {y:.16f} {z:.16f}\n")


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


def export_animation_from_structures(
    structures,
    shift=None,
    repeat=None,
    out="neb_guess_shifted.extxyz",
    out_format="extxyz"
):
    """
    Export visualization trajectory directly from pymatgen Structures.
    Used by cp2k mode so no POSCAR image folders are needed.
    """
    try:
        from ase.io import write
        from pymatgen.io.ase import AseAtomsAdaptor
    except ImportError:
        raise RuntimeError(
            "ASE and pymatgen's ASE adaptor are required for --shift / --repeat / extxyz export.\n"
            "Please install ASE, e.g.:\n"
            "  pip install ase\n"
            "or\n"
            "  conda install -c conda-forge ase"
        )

    adaptor = AseAtomsAdaptor()
    images = []
    for s in structures:
        a = adaptor.get_atoms(s)
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

    n_frames = len(new_path)

    if args.cp2k:
        n_ts = len(new_path[1:-1])
        include_endpoints = not args.no_cp2k_endpoints
        written = write_cp2k_xyz_images(
            new_path,
            outdir=args.cp2k_outdir,
            include_endpoints=include_endpoints,
            init_name=args.cp2k_init_name,
            final_name=args.cp2k_final_name,
            ts_prefix=args.cp2k_ts_prefix,
        )

        if not args.no_default_xyz:
            export_legacy_xyz_from_structures(
                new_path,
                out_name=os.path.join(args.cp2k_outdir, "neb_guess.xyz")
            )

        if not args.quiet:
            if include_endpoints:
                print(
                    f"[?] IDPP path generated. Frames: {n_frames}; "
                    f"CP2K xyz images written: {args.cp2k_init_name}, "
                    f"{args.cp2k_ts_prefix}-1.xyz .. {args.cp2k_ts_prefix}-{n_ts}.xyz, "
                    f"{args.cp2k_final_name}"
                )
            else:
                print(
                    f"[?] IDPP path generated. Frames: {n_frames}; "
                    f"CP2K xyz images written: {args.cp2k_ts_prefix}-1.xyz .. {args.cp2k_ts_prefix}-{n_ts}.xyz"
                )
            print(f"    output directory: {os.path.abspath(args.cp2k_outdir)}")
            if not args.no_default_xyz:
                print("[?] Legacy trajectory written: neb_guess.xyz (direct pymatgen Structure -> XYZ)")
    else:
        # Write POSCARs to 00/01/...
        for i, s in enumerate(new_path):
            image_dir = f"{i:02d}"
            os.makedirs(image_dir, exist_ok=True)
            s.to(fmt="poscar", filename=os.path.join(image_dir, "POSCAR"))

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
        if args.cp2k:
            export_animation_from_structures(
                structures=new_path,
                shift=args.shift,
                repeat=args.repeat,
                out=out_name,
                out_format=args.animfmt
            )
        else:
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
    if len(sys.argv) < 4 and not any(a in ("-h", "--help") for a in sys.argv[1:]):
        raise SystemError("Syntax Error! Run as: python idpp_v6.py ini/POSCAR fin/POSCAR 8 [cp2k]")
    main()
