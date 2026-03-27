"""Standalone ASE GUI with file polling"""
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("Usage: python poll_viewer.py <filepath> [interval_ms]")
        sys.exit(1)

    filepath = sys.argv[1]
    interval_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    from ase.io import read
    from ase.gui.gui import GUI
    from ase.gui.images import Images

    atoms = read(filepath)
    images = Images([atoms])
    gui = GUI(images)

    last_mtime = os.path.getmtime(filepath)

    def poll_file(gui):
        nonlocal last_mtime
        if not os.path.exists(filepath):
            return
        try:
            mtime = os.path.getmtime(filepath)
            if mtime != last_mtime:
                last_mtime = mtime
                new_atoms = read(filepath)
                gui.images.initialize([new_atoms])
                print(f"[Poll] Reloaded: {filepath}")
        except Exception as e:
            print(f"[Poll] Error: {e}")

    gui.repeat_poll(poll_file, interval_ms)
    print(f"Polling {filepath} every {interval_ms}ms")
    gui.run()


if __name__ == "__main__":
    main()
