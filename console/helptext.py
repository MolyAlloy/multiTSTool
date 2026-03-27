"""Help text display"""


def show_welcome():
    print("=" * 50)
    print("  Structool - Structure Manipulation Tool")
    print("=" * 50)
    print("Type 'help' for available commands")
    print()


def show_help():
    help_text = """
Available Commands:
-------------------
help              Show this help message
load <file>       Load structure from file
save <file>       Save structure to file
list              List atoms in current structure
select <criteria> Select atoms
translate <dx dy dz> Translate selected atoms
rotate <axis angle> Rotate selected atoms
undo              Undo last action
redo              Redo last undone action
info              Show structure information
exit/quit         Exit the program

Examples:
--------
load structure.xyz
select element O
translate 1.0 0.0 0.0
rotate z 90
"""
    print(help_text)
