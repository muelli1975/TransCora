"""Desktop entry point; no network operations or package installation."""
import tkinter as tk
from tkinter import messagebox


def main():
    root = tk.Tk()
    try:
        from transcora.gui.window import Window
        Window(root)
        root.mainloop()
    except Exception as error:
        messagebox.showerror("TransCora", str(error), parent=root)
        root.destroy()


if __name__ == "__main__":
    main()
