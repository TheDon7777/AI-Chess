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
To record and adapt their own strategies. Currently it is only utilizing the previous move data from each move by either of the models and not taking into account the entire game board picture for a more broad strategy.

** SETUP GUIDE **

Prerequisites:
^Ollama installed and configured
^Two models of your choice that fit in your VRAM (or CPU which I would not recommend as it could be really slow)
^The python package "python-chess" which you can install using pip install python-chess

Steps:
Launch Ollama by using command "ollama serve"
Download a model you would like to run for this (The best model I have found that is a smaller number of parameters is deepseek-r1:1.5b) and do that by typing ollama pull "insert model here" or ollama run "insert model"
Assuming you have python installed on your device enter nano "chess".py or replace the script name in quotes to whatever you'd like
Then finally run python or python3 (depending on your version) "chess".py
Select your models which if you enter the exact name of the models in the model name section you can select which model you would like to use that way.
And you can either play against two models that will have 10 attempts to make a valid move against you, or you could make them play against each other perhaps as a LLM benchmarking tool.

Have fun and don't lose to a 1.5b model in chess :)
