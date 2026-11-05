from copy import deepcopy
import pandas as pd
import pytest
from forecast_model import build_baseline, run_model, ModelUnavailable


def stock():
    t = pd.Timestamp('2025-12-31')
    prior = pd.Timestamp('2024-12-31')
    def frame(rows):
        return pd.DataFrame({t: list(rows.values()), prior: list(rows.values())}, index=list(rows))
    return {'symbol':'EXAMPLE','info':{'financialCurrency':'USD','statement_data_provider':'SEC Company Facts'},
        'income_stmt':frame({'Total Revenue':100,'Gross Profit':40,'Operating Income':20,'Net Income':15,'Pretax Income':20,'Tax Provision':5,'Interest Expense':0}),
        'balance_sheet':frame({'Total Assets':200,'Total Liabilities Net Minority Interest':100,'Stockholders Equity':100,
            'Cash And Cash Equivalents':20,'Accounts Receivable':20,'Inventory':10,'Accounts Payable':15,'Total Debt':10,'Ordinary Shares Number':10}),
        'cash_flow':frame({'Operating Cash Flow':15,'Capital Expenditure':0,'Depreciation And Amortization':0,'Stock Based Compensation':0})}


def baseline(data=None):
    return build_baseline(data or stock(), {'applicability_profile':{'key':'operating_company'}})


def drivers(**kw):
    return dict(revenue_growth=0, gross_margin=.4, operating_margin=.2, tax_rate=.25, capex_rate=0, da_rate=0, sbc_rate=0,
        receivables_days=73, inventory_days=365/6, payables_days=91.25, interest_rate=0, debt_draw=0, debt_repayment=0,
        equity_issuance=0, dividends=0, buybacks=0, **kw)


def assumptions(**kw):
    return dict(wacc=.1, terminal_growth=0, terminal_roic=.1, cash_in_bridge=20, nonoperating_assets=0, other_claims=0, **kw)


def model(years=None, value=None, base=None):
    return run_model(base or baseline(), years or [drivers() for _ in range(5)], value or assumptions(), 'Explicit test assumptions')


def test_flat_operating_firm_reconciles_and_matches_independent_perpetuity_value():
    result = model()
    assert result['dcf']['enterprise_value'] == pytest.approx(150)
    assert result['dcf']['equity_value'] == pytest.approx(160)
    assert result['dcf']['value_per_share'] == pytest.approx(16)
    for index,row in enumerate(result['forecasts'],1):
        assert row['cash'] == pytest.approx(20 + 15*index)
        assert row['balance_difference'] == pytest.approx(0)
        assert row['cash_difference'] == pytest.approx(0)
        assert row['fcff'] == pytest.approx(15)


def test_financing_interest_and_equity_roll_forward_without_double_counting():
    year = drivers(); year.update(debt_draw=10,debt_repayment=5,interest_rate=.1,equity_issuance=2,dividends=1,buybacks=3,sbc_rate=.01)
    result = model(years=[year] + [drivers() for _ in range(4)])
    first=result['forecasts'][0]
    assert first['debt']==15
    assert first['interest_expense']==1.25
    assert first['net_income']==pytest.approx(14.0625)
    assert first['operating_cash_flow']==pytest.approx(15.0625)
    assert first['financing_cash_flow']==3
    assert first['cash']==pytest.approx(38.0625)
    assert first['equity']==pytest.approx(113.0625)
    assert first['balance_difference']==pytest.approx(0)
    assert first['fcff']==15 # SBC is already an expense in EBIT and not added to DCF


def test_growth_changes_working_capital_and_terminal_reinvestment_is_required():
    year=drivers(); year['revenue_growth']=.1
    value=assumptions(); value.update(terminal_growth=.02, terminal_roic=.1)
    result=model(years=[year for _ in range(5)],value=value)
    first=result['forecasts'][0]
    assert first['change_working_capital']==pytest.approx(1.5)
    assert first['fcff']==pytest.approx(16.5-1.5)
    assert result['dcf']['terminal_reinvestment_rate']==pytest.approx(.2)
    expected_terminal=result['forecasts'][-1]['nopat']*1.02*.8/.08
    assert result['dcf']['terminal_value']==pytest.approx(expected_terminal)


def test_missing_or_nonreconciling_inputs_do_not_become_zeroes_and_actuals_are_unchanged():
    data=stock(); original=deepcopy(data['balance_sheet'])
    result=model(base=baseline(data))
    pd.testing.assert_frame_equal(data['balance_sheet'],original)
    data['balance_sheet']=data['balance_sheet'].drop('Inventory')
    unavailable=baseline(data)
    assert unavailable['status']=='unavailable'
    assert unavailable['values']['inventory'] is None
    with pytest.raises(ModelUnavailable): model(base=unavailable)
    data=stock(); data['balance_sheet'].loc['Stockholders Equity']+=5
    assert baseline(data)['status']=='unavailable'


def test_periods_sector_and_debt_definition_are_guarded():
    data=stock(); data['cash_flow'].columns=pd.to_datetime(['2025-09-30','2024-09-30'])
    assert baseline(data)['status']=='unavailable'
    assert build_baseline(stock(),{'applicability_profile':{'key':'financial_institution'}})['status']=='unavailable'
    data=stock(); data['info']['statement_data_provider']='Yahoo Finance'
    assert baseline(data)['values']['debt'] is None
    data['balance_sheet'].loc['Current Debt']=[2,2]
    data['balance_sheet'].loc['Long Term Debt']=[8,8]
    assert baseline(data)['values']['debt']==10


def test_no_automatic_funding_plug_and_no_valuation_of_an_unfunded_forecast():
    year=drivers(); year['capex_rate']=10
    result=model(years=[year]+[drivers() for _ in range(4)])
    assert result['forecasts'][0]['cash']<0
    assert result['forecasts'][0]['debt']==10
    assert result['warnings']
    assert result['dcf']['enterprise_value'] is None


def test_no_weighted_average_share_substitution_and_invalid_assumptions_rejected():
    data=stock(); data['balance_sheet']=data['balance_sheet'].drop('Ordinary Shares Number')
    assert model(base=baseline(data))['dcf']['value_per_share'] is None
    for key,value in [('revenue_growth',-1),('tax_rate',None),('capex_rate',float('nan')),('debt_draw',True),('debt_repayment',20)]:
        year=drivers(); year[key]=value
        with pytest.raises(ModelUnavailable): model(years=[year]+[drivers() for _ in range(4)])
    for key,value in [('wacc',0),('terminal_growth',.1),('terminal_roic',0),('cash_in_bridge',21)]:
        values=assumptions(); values[key]=value
        with pytest.raises(ModelUnavailable): model(value=values)


def test_latest_aligned_ttm_and_quarterly_balance_replace_older_annual_inputs():
    data=stock()
    for key in ('income_stmt','balance_sheet','cash_flow'):
        frame=data[key].copy();frame.columns=pd.to_datetime(['2026-06-30','2025-06-30'])
        if key=='income_stmt':frame.loc['Total Revenue']=[200,150]
        data['analysis_'+key]=frame
    data['analysis_basis']={'income':'trailing_twelve_months','cash_flow':'trailing_twelve_months','balance_sheet':'latest_quarter'}
    b=baseline(data)
    assert b['status']=='ready'
    assert b['period']=='2026-06-30'
    assert b['values']['revenue']==200
    assert b['flow_basis']=='trailing_twelve_months'
    assert b['historical_drivers']['revenue_growth']==pytest.approx(200/150-1)
    data['analysis_cash_flow'].columns=pd.to_datetime(['2026-03-31','2025-03-31'])
    assert baseline(data)['status']=='unavailable' # no silent fallback to the old annual set
