import os


# Keep unittest discovery on the deterministic planner unless a specific test
# explicitly overrides the mode in its own environment patch.
os.environ.setdefault("CLIPFORGE_PLANNER_MODE", "deterministic")
