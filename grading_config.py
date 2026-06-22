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

GRADING_RUBRIC = {
    4: {
        "level": "Distinguished",
        "description": "Consistently demonstrates deep understanding and flexible command of the standard.",
    },
    3: {
        "level": "Advancing",
        "description": "Demonstrates strong understanding of the standard with only minor gaps.",
    },
    2: {
        "level": "Proficient",
        "description": "Demonstrates the essential understanding needed for the standard.",
    },
    1: {
        "level": "Developing",
        "description": "Shows partial understanding, but important gaps remain.",
    },
    0: {
        "level": "Beginning / No Evidence",
        "description": "No evidence yet, insufficient evidence, or not yet assessable.",
    },
}

