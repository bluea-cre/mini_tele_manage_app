import os
import importlib.util
import tkinter as tk
from tkinter import ttk, messagebox
import functools
import argparse
import json


FUNCTIONS_DIR = "functions"
ORDER_FILE = os.path.join(FUNCTIONS_DIR, ".order")

DEBUG_LOG = False
CALL_DEEP = 0

# ANSI escape code to change text color
entry_color = "\033[94m"  # Blue color for entry
exit_color = "\033[91m"  # Red color for exit
highlight_color = [
    "\033[92m",  # Green
    "\033[93m",  # Yellow
    "\033[95m",  # Magenta
    "\033[96m",  # Cyan
    "\033[92m",  # Light Green
    "\033[93m",  # Light Yellow
    "\033[95m",  # Light Magenta
    "\033[96m",  # Light Cyan
]
reset_color = "\033[0m"  # Reset to normal color


def empty_function():
    print("Empty function\n")


def log_entry_exit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if DEBUG_LOG:
            global CALL_DEEP
            global entry_color
            global exit_color
            global highlight_color
            global reset_color
            func_color = highlight_color[CALL_DEEP % len(highlight_color)]
            indent = "    " * CALL_DEEP
            print(
                f"{indent}==> {entry_color}Entry: {func_color}{func.__name__}{reset_color} with arguments: {args}, {kwargs}"
            )
            CALL_DEEP += 1
            result = func(*args, **kwargs)
            CALL_DEEP -= 1
            indent = "    " * CALL_DEEP
            print(
                f"{indent}<== {exit_color}Exit: {func_color}{func.__name__}{reset_color} with result: {result}"
            )
        else:
            result = func(*args, **kwargs)
        return result

    return wrapper


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=1, ipady=1)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class FunctionRunnerApp:
    @log_entry_exit
    def __init__(self, root):
        self.root = root
        self.root.title("Function Runner App")

        self.load_window_size()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.function_rows = []

        self.edit_mode = False
        self.selected_row = None  # Track the currently focused row
        self.is_sorted_asc = (
            True  # Biến trạng thái để kiểm tra thứ tự sắp xếp (tăng dần hoặc giảm dần)
        )

        self.create_widgets()
        self.load_functions()

    @log_entry_exit
    def create_widgets(self):
        # Add main_frame to wrap all UI with margins
        main_frame = ttk.Frame(self.root)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # === First Row Frame ===
        first_row_frame = ttk.Frame(main_frame)
        first_row_frame.pack(pady=10)
        # === Control Frame ===
        control_frame = ttk.Frame(first_row_frame)  # Change parent to main_frame
        control_frame.grid(row=0, column=0)

        self.btn_add_function = ttk.Button(
            control_frame, text="Add New Function", command=self.add_new_function
        )
        self.btn_add_function.grid(row=0, column=0, padx=5)

        self.edit_save_button = ttk.Button(
            control_frame, text="Edit", command=self.toggle_edit_mode
        )
        self.edit_save_button.grid(row=0, column=1, padx=5)
        self.edit_tooltip = Tooltip(
            self.edit_save_button, "Edit function names and order"
        )

        # === Second Row Frame ===
        second_row_frame = ttk.Frame(main_frame)
        second_row_frame.pack(pady=(0, 20), fill="x")  # Ensure frame fills horizontally

        # Make the columns in second_row_frame adjust dynamically
        second_row_frame.grid_columnconfigure(
            0, weight=0
        )  # No expansion for the first column (Check/Uncheck)
        second_row_frame.grid_columnconfigure(
            1, weight=1
        )  # Middle column for move_frame to expand and center
        second_row_frame.grid_columnconfigure(
            2, weight=0
        )  # No expansion for the third column (Run All)

        # === Check/Uncheck Button on the Left ===
        self.btn_check_all = ttk.Button(
            second_row_frame, text="Check/Uncheck All", command=self.toggle_all
        )
        self.btn_check_all.grid(
            row=0, column=0, padx=(10, 10), sticky="w"
        )  # Align to the left (sticky="w")

        # === Run All Button on the Right ===
        self.btn_run_all = ttk.Button(
            second_row_frame, text="Run All", command=self.run_all
        )
        self.btn_run_all.grid(
            row=0, column=2, padx=(10, 34), sticky="e"
        )  # Align to the right (sticky="e")

        # === Move Frame in the Center ===
        move_frame = ttk.Frame(second_row_frame)  # Change parent to second_row_frame
        move_frame.grid(
            row=0, column=1, padx=(10, 10)
        )  # "ew" makes it stretch horizontally (center)

        # Move buttons inside move_frame
        self.btn_move_up = ttk.Button(
            move_frame, text="↑", width=6, command=self.move_up
        )
        self.btn_move_up.grid(row=0, column=1, padx=1, sticky="ew")

        self.btn_move_down = ttk.Button(
            move_frame, text="↓", width=6, command=self.move_down
        )
        self.btn_move_down.grid(row=0, column=2, padx=1)

        self.btn_move_top = ttk.Button(
            move_frame, text="⇈", width=6, command=self.move_top
        )
        self.btn_move_top.grid(row=0, column=3, padx=1)

        self.btn_move_bottom = ttk.Button(
            move_frame, text="⇊", width=6, command=self.move_bottom
        )
        self.btn_move_bottom.grid(row=0, column=4, padx=1)

        # === Sort Dropdown (Combobox) ===
        sort_options = ["Sort Alphabet", "Move Checked to Top"]  # New options
        self.sort_combobox = ttk.Combobox(
            move_frame, values=sort_options, state="readonly", width=20
        )
        self.sort_combobox.grid(row=0, column=6, padx=5)
        self.sort_combobox.bind("<<ComboboxSelected>>", self.on_sort_option_selected)
        self.sort_tooltip = Tooltip(self.sort_combobox, "Sort by option")

        self.move_buttons = [
            self.btn_move_up,
            self.btn_move_down,
            self.btn_move_top,
            self.btn_move_bottom,
            self.sort_combobox,
        ]
        for btn in self.move_buttons:
            btn.state(["disabled"])  # Initially disabled

        # === Functions Frame with Scroll ===
        functions_outer_frame = ttk.Frame(main_frame)
        functions_outer_frame.pack(pady=0, side="left", fill="both", expand=True)

        self.functions_canvas = tk.Canvas(functions_outer_frame, highlightthickness=0)
        self.functions_canvas.grid(row=0, column=0, sticky="nsew")

        # Add padding to the scrollbar from the right edge
        functions_scrollbar = ttk.Scrollbar(
            functions_outer_frame,
            orient="vertical",
            command=self.functions_canvas.yview,
        )
        functions_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=(1, 2))

        self.functions_canvas.configure(yscrollcommand=functions_scrollbar.set)

        self.functions_frame = ttk.Frame(self.functions_canvas)
        self.functions_window = self.functions_canvas.create_window(
            (0, 0), window=self.functions_frame, anchor="nw"
        )

        self.functions_frame.columnconfigure(2, weight=1)

        # Make sure the canvas resizes when the frame content size changes
        def on_canvas_configure(event):
            # Adjust the width of the canvas when the window is resized
            self.functions_canvas.itemconfig(self.functions_window, width=event.width)
            # Update the scroll region to the bounding box of all the content
            self.functions_canvas.configure(
                scrollregion=self.functions_canvas.bbox("all")
            )

        # Bind to the configure event to update the scrollregion when the content changes
        self.functions_canvas.bind("<Configure>", on_canvas_configure)

        # Enable mouse wheel scrolling for Windows
        def on_mouse_wheel(event):
            # Only scroll if the canvas or its children have focus
            if self.functions_canvas.winfo_viewable():
                self.functions_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind mouse wheel event to the main_frame to capture scroll over the canvas area
        main_frame.bind_all("<MouseWheel>", on_mouse_wheel)

        # Ensure functions_outer_frame expands properly
        functions_outer_frame.grid_rowconfigure(0, weight=1)
        functions_outer_frame.grid_columnconfigure(0, weight=1)

    @log_entry_exit
    def update_scrollregion(self):
        self.functions_canvas.configure(scrollregion=self.functions_canvas.bbox("all"))

    @log_entry_exit
    def update_order_file(self):
        # update .order file
        with open(ORDER_FILE, "w") as f:
            for row in self.function_rows:
                f.write(row["filename"] + "\n")

    @log_entry_exit
    def load_window_size(self):
        try:
            with open("window_size.json", "r") as f:
                size_data = json.load(f)
                width = size_data.get("width", 800)
                height = size_data.get("height", 600)
                self.root.geometry(f"{width}x{height}")
        except FileNotFoundError:
            self.root.geometry("800x600")

    @log_entry_exit
    def save_window_size(self):
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        size_data = {"width": width, "height": height}
        with open("window_size.json", "w") as f:
            json.dump(size_data, f)

    @log_entry_exit
    def on_close(self):
        self.update_order_file()
        self.save_window_size()
        self.root.destroy()

    @log_entry_exit
    def load_functions(self):
        if not os.path.exists(FUNCTIONS_DIR):
            os.makedirs(FUNCTIONS_DIR)
        all_files = [f for f in os.listdir(FUNCTIONS_DIR) if f.endswith(".py")]
        ordered_files = []
        if os.path.exists(ORDER_FILE):
            with open(ORDER_FILE, "r") as f:
                ordered_files = [line.strip() for line in f if line.strip()]
            # Filter files that still exist
            ordered_files = [f for f in ordered_files if f in all_files]
            # Add any new files not in .order
            for f in all_files:
                if f not in ordered_files:
                    ordered_files.append(f)
        else:
            ordered_files = sorted(all_files)
        # Populate function_rows based on ordered files
        self.function_rows = []
        for idx, filename in enumerate(ordered_files, start=1):
            self.add_function_row(idx, filename)

        self.update_order_file()
        self.reload_order()

    @log_entry_exit
    def add_function_row(self, idx, filename):
        frame = ttk.Frame(self.functions_frame)
        frame.pack(fill="x", pady=2)
        frame.columnconfigure(2, weight=1)

        var = tk.BooleanVar()
        chk = ttk.Checkbutton(frame, variable=var)
        chk.grid(row=0, column=0, padx=10)
        chk.bind("<Button-1>", lambda e, r=idx - 1: self.select_row(r))

        lbl_idx = ttk.Label(frame, text=f"No.{idx:03}")
        lbl_idx.grid(row=0, column=1, padx=10)

        name_var = tk.StringVar(value=filename)
        entry_name = ttk.Entry(frame, textvariable=name_var, state="readonly")
        entry_name.grid(row=0, column=2, padx=10, sticky="ew")
        entry_name.bind(
            "<FocusIn>", lambda e, r=idx - 1: self.select_row(r)
        )  # Update row index

        btn_run = ttk.Button(
            frame,
            text="Run",
            command=lambda nv=name_var, r=idx - 1: (
                self.select_row(r),
                self.run_function(nv.get()),
            )[-1],
        )
        btn_run.grid(row=0, column=3, padx=10)

        self.function_rows.append(
            {
                "frame": frame,
                "check_var": var,
                "filename": filename,
                "name_var": name_var,
                "entry": entry_name,
                "run_button": btn_run,
                "label_idx": lbl_idx,
            }
        )

    @log_entry_exit
    def select_row(self, row_idx):
        if row_idx < len(self.function_rows):
            self.selected_row = row_idx
            for idx, row in enumerate(self.function_rows):
                bg = "#d9d9d9" if idx == row_idx else "white"
                row["entry"].config(background=bg)
                row["frame"].config(
                    style="Highlighted.TFrame" if idx == row_idx else "TFrame"
                )

    @log_entry_exit
    def toggle_all(self):
        current_state = all(row["check_var"].get() for row in self.function_rows)
        for row in self.function_rows:
            row["check_var"].set(not current_state)

    @log_entry_exit
    def run_all(self):
        for row in self.function_rows:
            if row["check_var"].get():
                self.run_function(row["name_var"].get())

    @log_entry_exit
    def run_function(self, filename):
        filepath = os.path.join(FUNCTIONS_DIR, filename)
        spec = importlib.util.spec_from_file_location("module.name", filepath)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            if hasattr(module, "main"):
                module.main()
            else:
                print(f"{filename} has no main() function.")
        except Exception as e:
            print(f"Failed to run {filename}: {e}")

    @log_entry_exit
    def add_new_function(self):
        next_number = len(self.function_rows) + 1
        new_filename = f"function_{next_number:03}.py"
        new_filepath = os.path.join(FUNCTIONS_DIR, new_filename)
        with open(new_filepath, "w") as f:
            f.write(
                f'def main():\n    print("Running new function: File name: {new_filename}")\n'
            )
        self.add_function_row(len(self.function_rows) + 1, new_filename)
        self.reload_order()
        self.update_scrollregion()

    @log_entry_exit
    def move_up(self):
        if self.selected_row is not None and self.selected_row > 0:
            idx = self.selected_row
            self.function_rows[idx], self.function_rows[idx - 1] = (
                self.function_rows[idx - 1],
                self.function_rows[idx],
            )
            self.selected_row -= 1
            self.reload_order()

    @log_entry_exit
    def move_down(self):
        if (
            self.selected_row is not None
            and self.selected_row < len(self.function_rows) - 1
        ):
            idx = self.selected_row
            self.function_rows[idx], self.function_rows[idx + 1] = (
                self.function_rows[idx + 1],
                self.function_rows[idx],
            )
            self.selected_row += 1
            self.reload_order()

    @log_entry_exit
    def move_top(self):
        if self.selected_row is not None and self.selected_row > 0:
            row = self.function_rows.pop(self.selected_row)
            self.function_rows.insert(0, row)
            self.selected_row = 0
            self.reload_order()

    @log_entry_exit
    def move_bottom(self):
        if (
            self.selected_row is not None
            and self.selected_row < len(self.function_rows) - 1
        ):
            row = self.function_rows.pop(self.selected_row)
            self.function_rows.append(row)
            self.selected_row = len(self.function_rows) - 1
            self.reload_order()

    # Handle sort options selected
    @log_entry_exit
    def on_sort_option_selected(self, event):
        selected_option = self.sort_combobox.get()
        print(f"Selected option {selected_option}")
        if selected_option == "Sort Alphabet":
            self.sort_alphabet()
        elif selected_option == "Move Checked to Top":
            self.move_checked_to_top()

    @log_entry_exit
    def sort_alphabet(self):
        if messagebox.askyesno("Sort by Alphabet", "Bạn có chắc muốn sắp xếp?"):
            # Sort rows by filename, keeping all row components together
            if self.is_sorted_asc:
                self.function_rows.sort(
                    key=lambda x: x["name_var"].get(), reverse=True
                )  # Sắp xếp giảm dần
                self.is_sorted_asc = False  # Cập nhật trạng thái sắp xếp
            else:
                self.function_rows.sort(
                    key=lambda x: x["name_var"].get()
                )  # Sắp xếp tăng dần
                self.is_sorted_asc = True  # Cập nhật trạng thái sắp xếp
            # Clear existing frames from the canvas to avoid duplication
            for row in self.function_rows:
                row["frame"].pack_forget()
            # Re-pack frames in new order and update GUI
            self.reload_order()

    @log_entry_exit
    def move_checked_to_top(self):
        checked_rows = []
        unchecked_rows = []

        # Separate checked and unchecked rows
        for row in self.function_rows:
            if row["check_var"].get():
                checked_rows.append(row)
            else:
                unchecked_rows.append(row)

        # Combine checked items at the top with unchecked ones below
        self.function_rows = checked_rows + unchecked_rows

        # Clear existing frames from the canvas to avoid duplication
        for row in self.function_rows:
            row["frame"].pack_forget()

        # Update the UI to reflect the new order
        self.reload_order()

    @log_entry_exit
    def reload_order(self):
        # Configure style for highlighted frame
        style = ttk.Style()
        style.configure("Highlighted.TFrame", background="#d9d9d9")
        style.configure("TFrame", background="white")

        # Update UI elements for each row, ensuring label_idx reflects position
        for idx, row in enumerate(self.function_rows, start=1):
            # Synchronize filename with name_var
            row["filename"] = row["name_var"].get()
            # Update label_idx to reflect current position (always ascending)
            row["label_idx"].config(text=f"No.{idx:03}")
            # Update entry state based on edit mode
            row["entry"].config(state="normal" if self.edit_mode else "readonly")
            # Update run button command with current index
            row["run_button"].config(
                command=lambda nv=row["name_var"], r=idx - 1: (
                    self.select_row(r),
                    self.run_function(nv.get()),
                )[-1]
            )
            # Preserve check_var state
            row["check_var"].set(row["check_var"].get())
            # Re-pack the frame in the correct order
            row["frame"].pack(fill="x", pady=2)

        # Remove any extra rows
        while len(self.functions_frame.winfo_children()) > len(self.function_rows):
            self.functions_frame.winfo_children()[-1].pack_forget()
        self.function_rows = self.function_rows[: len(self.function_rows)]

        # Update move buttons state
        for btn in self.move_buttons:
            btn.state(["!disabled"] if self.edit_mode else ["disabled"])

        # Highlight selected row
        self.select_row(self.selected_row if self.selected_row is not None else -1)

        # Update scroll region to reflect new layout
        self.update_scrollregion()

    @log_entry_exit
    def toggle_edit_mode(self):
        if hasattr(self, "edit_tooltip") and self.edit_tooltip.tipwindow:
            self.edit_tooltip.hide_tip()
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.edit_save_button.config(text="Save")
        else:
            self.edit_save_button.config(text="Edit")
            self.save_order_and_names()
        self.reload_order()

    @log_entry_exit
    def save_order_and_names(self):
        for row in self.function_rows:
            new_name = (
                row["name_var"].get().replace(" ", "_")
            )  # Replace spaces with "_"
            if not new_name.endswith(".py"):
                new_name += ".py"
            old_name = row["filename"]
            old_path = os.path.join(FUNCTIONS_DIR, old_name)
            new_path = os.path.join(FUNCTIONS_DIR, new_name)
            if old_name != new_name:
                os.rename(old_path, new_path)
                print(f"Renamed {old_name} → {new_name}")
                row["filename"] = new_name

        self.update_order_file()
        print("Functions saved:", [row["filename"] for row in self.function_rows])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Enable debug (entry/exit) log or not
    DEBUG_LOG = args.debug

    try:
        root = tk.Tk()
        app = FunctionRunnerApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Application failed to start: {e}")
