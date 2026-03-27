#!/home/chenmu/.conda/envs/python/bin/python
# -*- coding: utf-8 -*-

import os
import argparse
from ase.io import read, write
from ase.geometry import wrap_positions
import numpy as np
import shutil
import re

def shift_structure(file_path, shift_vector, output_path=None, backup=True):
    atoms = read(file_path, format='vasp')
    scaled_pos = atoms.get_scaled_positions()
    new_pos = (scaled_pos + shift_vector) % 1.0
    atoms.set_scaled_positions(new_pos)

    if backup:
        backup_path = file_path + ".bak"
        shutil.copy(file_path, backup_path)
        print(f"备份原文件 -> {backup_path}")

    write(output_path or file_path, atoms, vasp5=True, direct=True)
    print(f"已平移并保存 -> {output_path or file_path}")

def process_ts_folder(folder_path, mode, shift_vector):
    folder_list = sorted([d for d in os.listdir(folder_path) if re.fullmatch(r'\d{2}', d)])
    full_paths = [os.path.join(folder_path, d) for d in folder_list]

    if mode == 'C':
        for path in full_paths[1:-1]:
            file = os.path.join(path, 'CONTCAR')
            if os.path.isfile(file):
                shift_structure(file, shift_vector)
    elif mode == 'P':
        for path in full_paths:
            file = os.path.join(path, 'POSCAR')
            if os.path.isfile(file):
                shift_structure(file, shift_vector)
    elif mode in ['CP', 'PC']:
        for path in full_paths[1:-1]:
            file = os.path.join(path, 'CONTCAR')
            if os.path.isfile(file):
                shift_structure(file, shift_vector)
        for path in [full_paths[0], full_paths[-1]]:
            file = os.path.join(path, 'POSCAR')
            if os.path.isfile(file):
                shift_structure(file, shift_vector)
    else:
        raise ValueError(f"不支持的模式: {mode}")

def prompt_for_shift():
    try:
        dx = float(input("X方向要加多少？"))
        dy = float(input("Y方向要加多少？"))
        dz = float(input("Z方向要加多少？"))
        return np.array([dx, dy, dz])
    except Exception:
        print("输入格式错误，请输入数字！")
        exit()

def main():
    parser = argparse.ArgumentParser(description="使用 ASE 平移 VASP POSCAR/CONTCAR 文件中的 Direct 坐标")
    parser.add_argument("target", help="目标文件或路径（如 POSCAR 或 包含 00~99 的过渡态文件夹）")
    parser.add_argument("--dx", type=float, help="X方向平移量")
    parser.add_argument("--dy", type=float, help="Y方向平移量")
    parser.add_argument("--dz", type=float, help="Z方向平移量")
    parser.add_argument("--mode", choices=["C", "P", "CP", "PC"], default="P", help="处理方式：C=中间CONTCAR，P=所有POSCAR，CP=POSCAR+CONTCAR")

    args = parser.parse_args()
    target = args.target

    if args.dx is None and args.dy is None and args.dz is None:
        print("未指定 --dx/--dy/--dz，将使用交互模式：")
        shift = prompt_for_shift()
    else:
        # 若部分为 None，默认填 0.0
        dx = args.dx if args.dx is not None else 0.0
        dy = args.dy if args.dy is not None else 0.0
        dz = args.dz if args.dz is not None else 0.0
        shift = np.array([dx, dy, dz])

    if os.path.isfile(target):
        shift_structure(target, shift)
    elif os.path.isdir(target):
        process_ts_folder(target, args.mode, shift)
    else:
        print(f"路径无效：{target}")

if __name__ == "__main__":
    main()
