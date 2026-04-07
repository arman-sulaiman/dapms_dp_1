GRADE_RULES = [
    (95, 'A+', 4.0, 'Outstanding'),
    (85, 'A', 4.0, 'Superlative'),
    (80, 'A-', 3.8, 'Excellent'),
    (75, 'B+', 3.3, 'Very Good'),
    (70, 'B', 3.0, 'Good'),
    (65, 'B-', 2.8, 'Average'),
    (60, 'C+', 2.5, 'Below Average'),
    (55, 'C', 2.2, 'Passing'),
    (50, 'D', 1.5, 'Probationary'),
    (0, 'F', 0.0, 'Fail'),
]


def get_grade(total):
    for cutoff, letter, gp, _ in GRADE_RULES:
        if total >= cutoff:
            return letter, gp
    return 'F', 0.0


def get_assessment_label(total):
    for cutoff, _, _, label in GRADE_RULES:
        if total >= cutoff:
            return label
    return 'Fail'
