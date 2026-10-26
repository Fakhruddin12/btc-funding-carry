"""Report the CV's dated-futures risk metrics from a regenerated hourly ledger."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def main():
    ledger_path = ROOT / 'reports/inverse_cost_cash_gate_cost12_7_hourly.csv'
    if not ledger_path.is_file():
        raise SystemExit('First run extract_inputs.py and inverse.py from relative_value/.')
    h = pd.read_csv(ledger_path, index_col=0, parse_dates=True)
    initial = float(h.loc[:'2022', 'nav'].iloc[-1])
    v = h.loc['2023':, 'nav']
    daily = v.resample('D').last()
    returns = daily.pct_change()
    returns.iloc[0] = daily.iloc[0] / initial - 1
    cash = (1 + h.loc['2023':, 'cash_benchmark_return']).resample('D').prod() - 1
    excess = returns - cash
    hourly_peak = np.maximum.accumulate(np.r_[initial, v.to_numpy()])[1:]
    daily_peak = np.maximum.accumulate(np.r_[initial, daily.to_numpy()])[1:]
    results = {
        'evaluation_start': str(v.index[0]),
        'evaluation_end': str(v.index[-1]),
        'annualisation_days': 365,
        'annualised_cash_excess_sharpe': float(np.sqrt(365) * excess.mean() / excess.std(ddof=1)),
        'maximum_drawdown_hourly_nav': float((v.to_numpy() / hourly_peak - 1).min()),
        'maximum_drawdown_daily_nav': float((daily.to_numpy() / daily_peak - 1).min()),
        'initial_capital_full_2021_simulation_usd': 100000,
        'nav_at_start_of_2023_evaluation_usd': initial,
        'interpretation': 'Retrospective net-return backtest with cash interest and assumed costs. Test capital is not a proven capacity limit.'
    }
    destination = ROOT / 'reports/cv_risk_metrics.json'
    destination.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
