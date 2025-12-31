Examples
- ClaudeV2-output.wav: input audio used for the proof-of-concept run.
- ClaudeV2-output_poly_fixed.mid/.txt: polyphonic transcription results (Basic Pitch).
- ClaudeV2-output.mid/.txt: monophonic fallback results for comparison.

Re-run locally
- conda env create -f ../environment.yml -n audio2llm
- conda activate audio2llm
- python -m audio2llm.cli ClaudeV2-output.wav --out-midi out.mid --out-text out.txt --prefer-polyphonic
