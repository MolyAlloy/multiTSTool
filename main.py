"""Main entry point for multiTS"""
from gui.control_window import ControlWindow
from app.controller import Controller


def main():
    controller = Controller()
    window = ControlWindow(controller)
    window.run()


if __name__ == "__main__":
    main()