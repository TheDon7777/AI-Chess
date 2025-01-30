import tkinter as tk
from tkinter import messagebox, simpledialog
import chess
import threading
import subprocess
import re
import time
import logging

# -------------------
# Config & Globals
# -------------------
BOARD_SIZE = 480
SQUARE_SIZE = BOARD_SIZE // 8
MODEL_MOVE_TIMEOUT = 30
MAX_RETRIES = 5     # Max invalid attempts per model before skipping
MAX_TOTAL_FAIL = 10 # Max combined invalid attempts (model1 + model2) on a single turn
game_speed = 1.0

# Default model names (must be valid as pulled by Ollama)
model1_wins = 0
model2_wins = 0
model1_name = "deepseek-r1:1.5b"
model2_name = "deepseek-r1:1.5b"

# Logging setup
logging.basicConfig(
    filename='chess_model_moves.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Unicode piece symbols
PIECE_SYMBOLS = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟︎','n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
}

def draw_board(canvas, board):
    """
    Draws the chessboard and pieces using Unicode symbols.
    """
    canvas.delete("all")
    colors = ["#F0D9B5", "#B58863"]
    for i in range(8):
        for j in range(8):
            color = colors[(i + j) % 2]
            x1 = j * SQUARE_SIZE
            y1 = i * SQUARE_SIZE
            x2 = x1 + SQUARE_SIZE
            y2 = y1 + SQUARE_SIZE
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)

            square = chess.square(j, 7 - i)
            piece = board.piece_at(square)
            if piece:
                symbol = PIECE_SYMBOLS.get(piece.symbol(), '')
                if symbol:
                    canvas.create_text(
                        x1 + SQUARE_SIZE/2,
                        y1 + SQUARE_SIZE/2,
                        text=symbol,
                        font=("Helvetica", int(SQUARE_SIZE / 1.5)),
                        fill="black" if piece.color == chess.WHITE else "white"
                    )

def format_legal_moves_flat(board):
    """Returns a comma-separated list of all legal moves in UCI format."""
    return ", ".join(move.uci() for move in board.legal_moves)


# ------------------------------------------
# Strict UCI-only Model Interaction (via stdin)
# ------------------------------------------
def get_strict_uci_move(model_name, board, move_history):
    """
    Pipes the prompt via stdin to 'ollama run <model_name>'.
    Logs everything, tries to parse the first valid UCI move.
    """
    fen = board.fen()
    legal_moves = list(board.legal_moves)
    legal_str = format_legal_moves_flat(board)
    hist_str = " ".join(m.uci() for m in move_history)

    prompt = (
        f"Chess state: {fen}\n"
        f"Move history: {hist_str}\n"
        f"Legal moves: {legal_str}\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "Output ONLY one line containing exactly one valid UCI move from the list above.\n"
        "Do NOT provide any commentary, text, or explanation.\n"
        "Example: e2e4\n\n"
        "Please provide your UCI move now:"
    )

    command = ["ollama", "run", model_name]

    logging.info(f"[{model_name}] About to run command: {command}")
    logging.info(f"[{model_name}] Prompt:\n{prompt}")

    try:
        result = subprocess.run(
            command,
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=MODEL_MOVE_TIMEOUT,
            text=True
        )

        logging.info(f"[{model_name}] Return code: {result.returncode}")
        if result.stderr:
            logging.info(f"[{model_name}] STDERR:\n{result.stderr}")
        logging.info(f"[{model_name}] STDOUT:\n{result.stdout}")

        # Attempt to parse out a valid UCI move from stdout
        matches = re.findall(r'\b([a-h][1-8][a-h][1-8][qQrRbBnN]?)\b', result.stdout)
        for candidate in matches:
            if candidate in [m.uci() for m in legal_moves]:
                logging.info(f"[{model_name}] Found valid move: {candidate}")
                return candidate

        logging.warning(f"[{model_name}] No valid UCI move found in response.")
        return None

    except subprocess.TimeoutExpired:
        logging.error(f"[{model_name}] Timed out after {MODEL_MOVE_TIMEOUT}s.")
        return None
    except Exception as e:
        logging.error(f"[{model_name}] Error running subprocess: {e}")
        return None

def run_move_with_retries(model_name, board, move_history, attempts_ref, done_callback):
    """
    Up to MAX_RETRIES, tries to get a valid move from the model. 
    If none found, done_callback(None).
    """
    move_uci = None
    for attempt in range(MAX_RETRIES):
        if board.is_game_over():
            break
        candidate = get_strict_uci_move(model_name, board, move_history)
        if candidate is not None:
            if candidate in [m.uci() for m in board.legal_moves]:
                move_uci = candidate
                break
            else:
                logging.warning(f"[{model_name}] Attempt {attempt+1}/{MAX_RETRIES}: Invalid move {candidate}")
                attempts_ref[0] += 1
        else:
            attempts_ref[0] += 1

        if move_uci is None and attempt < MAX_RETRIES - 1:
            print(f"{model_name}: Retrying move ({attempt+1}/{MAX_RETRIES})...")
            time.sleep(1)

    done_callback(move_uci)

# ----------------------------------------------
# Main GUI Class
# ----------------------------------------------
class ChessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess (Strict UCI) + Skipping after 5 + Old Prompt Logic")

        self.board = chess.Board()
        self.canvas = tk.Canvas(root, width=BOARD_SIZE, height=BOARD_SIZE)
        self.canvas.grid(row=0, column=0, columnspan=4)

        tk.Label(root, text="Model 1 Name:").grid(row=1, column=0, sticky='e')
        self.model1_entry = tk.Entry(root)
        self.model1_entry.insert(0, model1_name)
        self.model1_entry.grid(row=1, column=1, sticky='w')

        tk.Label(root, text="Model 2 Name:").grid(row=2, column=0, sticky='e')
        self.model2_entry = tk.Entry(root)
        self.model2_entry.insert(0, model2_name)
        self.model2_entry.grid(row=2, column=1, sticky='w')

        self.start_button = tk.Button(root, text="Start Normal (Model vs Model)",
                                      command=self.start_normal_game)
        self.start_button.grid(row=1, column=3, rowspan=2, padx=5, pady=5)

        self.train_button = tk.Button(root, text="Start Training (You vs 2 Models)",
                                      command=self.start_training)
        self.train_button.grid(row=3, column=3, padx=5, pady=5)

        self.speed_label = tk.Label(root, text="Game Speed (sec):")
        self.speed_label.grid(row=3, column=0, sticky='e')
        self.speed_scale = tk.Scale(root, from_=0.5, to=5.0, resolution=0.5,
                                    orient=tk.HORIZONTAL, command=self.update_speed)
        self.speed_scale.set(game_speed)
        self.speed_scale.grid(row=3, column=1, sticky='w')

        self.tally_label = tk.Label(root, text="Tally:")
        self.tally_label.grid(row=4, column=0, sticky='e')
        self.tally_text = tk.Label(root, text="Model 1: 0 wins\nModel 2: 0 wins")
        self.tally_text.grid(row=4, column=1, sticky='w')

        self.game_running = False
        self.training_mode = False

        self.board.reset()
        draw_board(self.canvas, self.board)

    def update_speed(self, val):
        global game_speed
        game_speed = float(val)

    def update_tally(self):
        self.tally_text.config(text=f"{model1_name}: {model1_wins} wins\n{model2_name}: {model2_wins} wins")

    def _initialize_game(self):
        global model1_name, model2_name
        model1_name = self.model1_entry.get().strip()
        model2_name = self.model2_entry.get().strip()

        self.board.reset()
        draw_board(self.canvas, self.board)
        self.game_running = True

        self.start_button.config(state=tk.DISABLED)
        self.train_button.config(state=tk.DISABLED)

    def _finalize_game(self):
        self.game_running = False
        self.start_button.config(state=tk.NORMAL)
        self.train_button.config(state=tk.NORMAL)

    def _handle_game_over(self):
        global model1_wins, model2_wins
        self.game_running = False
        if self.board.is_checkmate():
            if self.board.turn == chess.WHITE:
                winner = model2_name if not self.training_mode else "Models"
                if not self.training_mode:
                    model2_wins += 1
            else:
                winner = model1_name if not self.training_mode else "You"
                if not self.training_mode:
                    model1_wins += 1
            messagebox.showinfo("Game Over", f"Checkmate! {winner} wins!")
        elif (self.board.is_stalemate() or
              self.board.is_insufficient_material() or
              self.board.can_claim_draw()):
            messagebox.showinfo("Game Over", "It's a draw.")
        else:
            messagebox.showinfo("Game Over", "The game ended.")

        self.update_tally()
        self._finalize_game()

    def _redraw_after_delay(self):
        draw_board(self.canvas, self.board)
        self.root.update_idletasks()
        time.sleep(game_speed)

    # -----------------------
    # Normal Mode: Model vs Model
    # -----------------------
    def start_normal_game(self):
        if self.game_running:
            messagebox.showinfo("Game Running", "A game is already running.")
            return
        self.training_mode = False
        self._initialize_game()

        t = threading.Thread(target=self._normal_mode_loop, daemon=True)
        t.start()

    def _normal_mode_loop(self):
        global model1_wins, model2_wins

        move_history = []
        while self.game_running and not self.board.is_game_over():
            current_model = model1_name if self.board.turn == chess.WHITE else model2_name

            attempts_ref = [0]
            result_holder = []
            ev = threading.Event()

            def done_cb(chosen_uci):
                result_holder.append(chosen_uci)
                ev.set()

            worker = threading.Thread(
                target=run_move_with_retries,
                args=(current_model, self.board, move_history, attempts_ref, done_cb),
                daemon=True
            )
            worker.start()
            ev.wait(MODEL_MOVE_TIMEOUT + 10)

            if not result_holder:
                # No response
                print(f"{current_model} timed out or gave no response.")
                self._finalize_game()
                return

            chosen_move = result_holder[0]
            if chosen_move is None:
                # The model used all attempts but no valid move => skip
                if attempts_ref[0] >= MAX_RETRIES:
                    print(f"{current_model} exhausted {MAX_RETRIES} attempts. Skipping turn...")
                    # Switch to the other model
                    self.board.turn = not self.board.turn
                    self._redraw_after_delay()
                    continue  # Keep the while loop going
                else:
                    print(f"No valid move from {current_model}, attempts={attempts_ref[0]}. Ending.")
                    self._finalize_game()
                    return
            else:
                # Valid move
                move_obj = chess.Move.from_uci(chosen_move)
                if move_obj in self.board.legal_moves:
                    self.board.push(move_obj)
                    move_history.append(move_obj)
                    self._redraw_after_delay()
                else:
                    print(f"Illegal move by {current_model}: {chosen_move}")
                    messagebox.showerror("Illegal Move", f"{current_model} made an illegal move: {chosen_move}")
                    self._finalize_game()
                    return

        if self.board.is_game_over():
            self._handle_game_over()

    # ------------------------
    # Training Mode: You (White) vs. Two Models (Black)
    # ------------------------
    def start_training(self):
        if self.game_running:
            messagebox.showinfo("Game Running", "A game is already running.")
            return

        self.training_mode = True
        self._initialize_game()

        self._training_step()

    def _training_step(self):
        if not self.game_running or self.board.is_game_over():
            self._handle_game_over()
            return

        if self.board.turn == chess.WHITE:
            self._prompt_user_move()  # OLD logic: if invalid, end game
        else:
            self._attempt_coop_models()

    def _prompt_user_move(self):
        """
        Old logic: If user enters invalid/illegal/no move, finalize game 
        instead of re-prompting.
        """
        user_move = simpledialog.askstring(
            "Your Move (White)",
            "Enter a move in UCI format (e2e4) or type 'help' to see possible moves:",
            parent=self.root
        )
        if not user_move:
            messagebox.showwarning("No Move", "You didn't provide a move. Game ended.")
            self._finalize_game()
            return

        user_move = user_move.strip().lower()
        if user_move in ("help", "?"):
            moves_str = format_legal_moves_flat(self.board)
            messagebox.showinfo("Available Moves", moves_str)
            # End the game here, as per old logic
            self._finalize_game()
            return

        # Try parse
        try:
            move_obj = chess.Move.from_uci(user_move)
        except ValueError:
            messagebox.showerror("Invalid Move", f"{user_move} is not valid syntax.")
            self._finalize_game()
            return

        # Check legality
        if move_obj not in self.board.legal_moves:
            messagebox.showerror("Illegal Move", f"{user_move} is not a legal move.")
            self._finalize_game()
            return

        # If valid
        self.board.push(move_obj)
        draw_board(self.canvas, self.board)
        self.root.update_idletasks()
        time.sleep(game_speed)

        # Continue training step
        self.root.after(50, self._training_step)

    def _attempt_coop_models(self):
        thread = threading.Thread(target=self._coop_worker, daemon=True)
        thread.start()

    def _coop_worker(self):
        move_history = list(self.board.move_stack)
        fail_count_1 = 0
        fail_count_2 = 0

        while (fail_count_1 + fail_count_2) < MAX_TOTAL_FAIL:
            current_model = model1_name if fail_count_1 <= fail_count_2 else model2_name

            attempts_ref = [0]
            result_holder = []
            ev = threading.Event()

            def done_cb(chosen_uci):
                result_holder.append(chosen_uci)
                ev.set()

            t = threading.Thread(
                target=run_move_with_retries,
                args=(current_model, self.board, move_history, attempts_ref, done_cb),
                daemon=True
            )
            t.start()
            ev.wait(MODEL_MOVE_TIMEOUT + 10)

            if result_holder:
                chosen = result_holder[0]
                if chosen is None:
                    if current_model == model1_name:
                        fail_count_1 += 5
                        print(f"{current_model} exhausted 5 attempts. Switching to {model2_name}.")
                    else:
                        fail_count_2 += 5
                        print(f"{current_model} exhausted 5 attempts. Switching to {model1_name}.")
                else:
                    # Found a valid move
                    self._coop_finished(chosen)
                    return
            else:
                # timed out => treat as 5 fails
                if current_model == model1_name:
                    fail_count_1 += 5
                else:
                    fail_count_2 += 5

            time.sleep(1)

        # If fail_count_1+fail_count_2 >= MAX_TOTAL_FAIL => skip
        self._coop_finished(None)

    def _coop_finished(self, move_uci):
        def finalize():
            if not self.game_running or self.board.is_game_over():
                self._handle_game_over()
                return

            if move_uci is None:
                messagebox.showwarning(
                    "Skip",
                    "Models exceeded 10 invalid attempts. It's your turn again."
                )
                self.board.turn = chess.WHITE
                self.root.after(50, self._training_step)
            else:
                move_obj = chess.Move.from_uci(move_uci)
                if move_obj in self.board.legal_moves:
                    self.board.push(move_obj)
                    draw_board(self.canvas, self.board)
                    self.root.update_idletasks()
                    time.sleep(game_speed)
                    self._training_step()
                else:
                    messagebox.showerror("Illegal Move", f"Models made illegal move {move_uci}")
                    self._finalize_game()

        self.root.after(0, finalize)


if __name__ == "__main__":
    root = tk.Tk()
    gui = ChessGUI(root)
    root.mainloop()
