from typing import Optional, Union
import numpy as np
import scipy.stats as stats
from scipy.optimize import minimize

np.random.seed(861)

def add_grade_to_rank(rank_lines: list[str], grade: float, fmt: Optional[str] = "") -> list[str]:
  i = 0
  if len(rank_lines) > 0:
    for i, line in enumerate(rank_lines):
      current_grade = line[9:]
      if not line[9].isdigit():
        i = 0
        for i, c in enumerate(current_grade):
          if c.isdigit(): break
        current_grade = current_grade[i:-i]

      if grade >= float(current_grade): break
    else: i += 1

  rank_lines.insert(i, f"**{(i + 1):>2}** - {fmt}{grade}{fmt}")
  for j in range(i + 1, len(rank_lines)):
    rank_lines[j] = f"**{(j + 1):>2}{rank_lines[j][4:]}"

  return rank_lines

def filter_real_grades(rank_lines: list[str]) -> list[float]:
  return [line for line in rank_lines if line[9].isdigit()]

def parse_message_rank(content: str) -> tuple[str, list[str], list[str]]:
  lines = content.splitlines()
  title = lines[0]
  
  lines = lines[1:]
  data_end = len(lines) + 1
  try:
    data_end = lines.index('') + 1
  except ValueError:
    lines.append('')

  return title, lines[:data_end], lines[data_end:]

def build_rank_message(title, data_lines: list[str], rank_lines: list[str]) -> str:
  return title + '\n' + '\n'.join(data_lines) + '\n' + '\n'.join(rank_lines)

DATA_LINES_MAPPING = {
  'Barème': ('scale', 20, int),
  'Minimum': ('min', None, float),
  'Maximum': ('max', None, float),
  'Médiane': ('median', None, float),
  'Moyenne': ('mean', None, float),
  'Écart-type': ('std', 0., float),
  'Nombre total de notes': ('total', None, int),
}
def parse_data_lines(data_lines: list[str]) -> dict[str, Union[int, float]]:
  data = {}
  for line in data_lines:
    if ':' not in line: continue
    key, value = line.split(':', 1)
    value = value.strip()

    key, _, parse = DATA_LINES_MAPPING[key[1:].strip()[2:-2].strip()]
    data[key] = parse(value)

  for _, (key, default, _) in DATA_LINES_MAPPING.items():
    if key not in data:
      data[key] = default

  return data

def build_data_lines(data: dict[str, Union[int, float]]) -> list[str]:
  return [f"> **{name}** : {data[key]}" for name, (key, _, _) in DATA_LINES_MAPPING.items() if key in data and data[key]] + ['']

def fill_rank(data: dict[str, Union[int, float]], rank_lines: list[str]) -> list[str]:
  if data['total'] is None or data['min'] is None or data['max'] is None or data['median'] is None or data['mean'] is None:
    return rank_lines

  known_grades = [float(line[9:]) for line in rank_lines]

  if not data['min'] in known_grades:
    known_grades.append(data['min'])
    rank_lines = add_grade_to_rank(rank_lines, data['min'])
  if not data['max'] in known_grades:
    known_grades.append(data['max'])
    rank_lines = add_grade_to_rank(rank_lines, data['max'])

  missing_grades = estimate_missing_grades(
    known_grades,
    data['total'],
    data['min'],
    data['max'],
    data['median'],
    data['mean'],
    data['std']
  )

  for grade in missing_grades:
    rank_lines = add_grade_to_rank(rank_lines, grade, '||')

  return rank_lines

def estimate_missing_grades(known_grades: list[float], num_total_grades:int, min_grade:float, max_grade:float, median_target:float, mean_target:float, std_dev_target:float=0.) -> list[float]:
  known_grades = np.array(known_grades)

  n_known = len(known_grades)
  n_missing = num_total_grades - n_known

  if n_missing <= 0:
      return []

  def error_function(missing_grades):
    all_grades = np.concatenate([known_grades, missing_grades])
    current_mean = np.mean(all_grades)
    current_std_dev = np.std(all_grades)
    current_median = np.median(all_grades)

    mean_error = abs(current_mean - mean_target)
    std_dev_error = (std_dev_target != 0) * abs(current_std_dev - std_dev_target)
    median_error = abs(current_median - median_target)

    return 2 * std_dev_error + median_error + 7 * mean_error
  
  mu, sigma = stats.norm.fit(known_grades)
  lower, upper = (min_grade - mu) / sigma, (max_grade - mu) / sigma
  initial_guess = stats.truncnorm.rvs(lower, upper, loc=mu, scale=sigma, size=n_missing)
  initial_guess = np.round(initial_guess, 1)

  bounds = [(min_grade, max_grade)] * n_missing
  result = minimize(error_function, initial_guess, bounds=bounds, method='L-BFGS-B', tol=1e-6)

  return np.sort(np.round(result.x, 1)).tolist()
