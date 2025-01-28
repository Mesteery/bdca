from typing import Optional, Union
import numpy as np
import scipy.stats as stats
from scipy.optimize import minimize

np.random.seed(861)

def add_grade_to_rank(ranks: list[str], grades: list[float], fmt: Optional[str] = "") -> list[str]:
  if len(ranks) > 0:
    grades = grades.copy()
    new_ranks = []

    for og_grade in ranks:
      current_grade = float(og_grade)

      while len(grades) > 0 and grades[-1] >= current_grade:
        new_ranks.append(f"{fmt}{grades.pop():g}{fmt}")
      
      new_ranks.append(og_grade)
    else:
      new_ranks.extend([f"{fmt}{grade:g}{fmt}" for grade in grades[::-1]])

    return new_ranks
  
  return [f"{fmt}{grade:g}{fmt}" for grade in grades[::-1]]

def build_rank_lines(ranks: list[str]) -> list[str]:
  return [f"**{i + 1:>2}** - {rank}" for i, rank in enumerate(ranks)]

def filter_real_grades(ranks: list[str]) -> list[str]:
  return [grade for grade in ranks if grade[0].isdigit()]

def parse_message_rank(content: str) -> tuple[str, list[str], list[str]]:
  lines = content.splitlines()
  title = lines[0]
  
  lines = lines[1:]
  data_end = len(lines) + 1
  try:
    data_end = lines.index('') + 1
  except ValueError:
    lines.append('')

  rank_lines = lines[data_end:]
  ranks = [line.split('-', 1)[1].strip() for line in rank_lines]

  return title, lines[:data_end], ranks

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

def fill_rank(data: dict[str, Union[int, float]], ranks: list[str]) -> list[str]:
  if data['total'] is None or data['min'] is None or data['max'] is None or data['median'] is None or data['mean'] is None:
    return ranks

  known_grades = list(map(float, ranks))

  min = None
  max = None
  if not data['min'] in known_grades:
    known_grades.append(data['min'])
    min = data['min']
  if not data['max'] in known_grades:
    known_grades.append(data['max'])
    max = data['max']

  missing_grades = estimate_missing_grades(
    known_grades,
    data['total'],
    data['min'],
    data['max'],
    data['median'],
    data['mean'],
    data['std']
  )
  
  if max is not None:
    missing_grades.append(max)
  if min is not None:
    missing_grades.insert(0, min)

  print(missing_grades)

  return add_grade_to_rank(ranks, missing_grades, '||')

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

  bounds = [(min_grade, max_grade)] * n_missing
  result = minimize(error_function, initial_guess, bounds=bounds, method='L-BFGS-B', tol=1e-6)

  return np.sort(np.round(result.x, 2)).tolist()
