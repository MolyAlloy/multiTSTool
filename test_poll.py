"""Test polling feature with ASE GUI"""
import os
import time
import threading

# Create a test xyz file
test_file = "test_poll.xyz"

def write_structure(filename, z_offset=0.0):
    """Write a simple water molecule with z offset"""
    content = f"""3
Water molecule z={z_offset:.1f}
O  0.000  0.000  {z_offset:.3f}
H  0.757  0.586  {z_offset + 0.557:.3f}
H -0.757  0.586  {z_offset + 0.557:.3f}
"""
    with open(filename, 'w') as f:
        f.write(content)
    print(f"Wrote {filename} with z_offset={z_offset}")

# Initial file
write_structure(test_file, 0.0)

# Simulate file modification in background
def modify_file():
    for i in range(10):
        time.sleep(3)
        z = i * 0.5
        write_structure(test_file, z)
        print(f"[Modifier] Updated file, z={z}")

modifier = threading.Thread(target=modify_file, daemon=True)
modifier.start()

# Now test the polling viewer
from gui.ase_viewer import ASEViewer, ASE_AVAILABLE

if ASE_AVAILABLE:
    print("Opening ASE GUI with polling (1s interval)...")
    print("File will be modified every 3 seconds.")
    print("Close the ASE window to stop the test.")
    
    from ase.io import read
    from ase.gui.gui import GUI
    from ase.gui.images import Images
    
    atoms = read(test_file)
    images = Images([atoms])
    gui = GUI(images)
    
    last_mtime = os.path.getmtime(test_file)
    
    def poll_file(gui_self):
        global last_mtime
        if not os.path.exists(test_file):
            return
        try:
            mtime = os.path.getmtime(test_file)
            if mtime != last_mtime:
                last_mtime = mtime
                new_atoms = read(test_file)
                gui_self.images.initialize([new_atoms])
                print(f"[Poll] Reloaded!")
        except Exception as e:
            print(f"[Poll] Error: {e}")
    
    gui.repeat_poll(poll_file, 1000)
    gui.run()
    
    print("GUI closed.")
else:
    print("ASE not available!")
