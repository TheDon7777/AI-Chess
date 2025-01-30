# AI-Chess

A Tkinter-based chess GUI that pits two Ollama models against each other (normal mode) or allows you to train against them (training mode). It enforces strict UCI-only output from the models, skips a model’s turn if it makes 5 invalid attempts, and uses the old prompting logic in training mode (invalid user moves end the game).

Features
Strict UCI Parsing

Models must output a single valid UCI move (e.g., e2e4).
Extra text is ignored via a regex, and invalid moves trigger retries or skipping.
Auto-Skip After 5 Invalid Moves

In normal mode (Model vs. Model), if a model tries 5 invalid moves, it skips to the other model immediately.
Training Mode (You vs. Models) with Old Prompting Logic

You always move Black in training mode.
If you provide an invalid/illegal move, the game ends (no re-prompting).

Full Logging
Logs everything to chess_model_moves.log (command, prompt, model stdout/stderr, chosen moves).

Notes:
I know there will be a ton of inconsistencies with my code, but it's my first public repo what can you say?
The training mode is currently a placeholder for logic that I am going to look to implement later that will allow the models to use a prompt based reinforcement learning function
To record and adapt their own strategies.
