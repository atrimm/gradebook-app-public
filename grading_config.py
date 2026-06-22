from pathlib import Path

GRADEBOOK_CSV_PATH = Path(
    "~/Library/CloudStorage/GoogleDrive-atrimm@imsa.edu/My Drive/Gradebook App/Testing/gradebook.csv"
).expanduser()

GRADE_THRESHOLDS = {
    "A": {
        "frac1": 1.00,
        "frac2": 1.00,
        "frac3": 0.75,
        "frac4": 0.60,
    },
    "B": {
        "frac1": 1.00,
        "frac2": 1.00,
        "frac3": 0.50,
    },
    "C": {
        "frac1": 0.80,
        "frac2": 0.75,
        "frac3": 0.25,
    },
    "C-": {
        "frac1": 0.70,
        "frac2": 0.50,
        "frac3": 0.10,
    }
}

