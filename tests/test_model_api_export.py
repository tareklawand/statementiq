from io import BytesIO
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
import main
from model_export import export_workbook
from test_forecast_model import baseline, drivers, assumptions, model


def request():
    base=baseline()
    return {'symbol':'EXAMPLE','baseline_sha256':base['input_sha256'],'years':[drivers() for _ in range(5)],'valuation':assumptions(),'note':'Explicit assumptions'}


def test_model_uses_server_actuals_and_rejects_stale_or_supplied_financials(monkeypatch):
    monkeypatch.setattr(main,'load_model_baseline',lambda symbol: baseline())
    client=TestClient(main.app)
    body=request()
    response=client.post('/api/research/forecast',json=body)
    assert response.status_code==200
    assert response.json()['dcf']['enterprise_value']==pytest.approx(150)
    body['baseline_sha256']='b'*64
    assert client.post('/api/research/forecast',json=body).status_code==409
    body=request();body['actuals']={'revenue':10000000}
    assert client.post('/api/research/forecast',json=body).status_code==422
    body=request();body['years'][0]['tax_rate']=None
    assert client.post('/api/research/forecast',json=body).status_code==422


def test_oversized_model_requests_are_rejected_before_source_fetch(monkeypatch):
    monkeypatch.setattr(main,'load_model_baseline',lambda symbol: pytest.fail('Oversized input must not fetch financial sources'))
    response=TestClient(main.app).post('/api/research/forecast',content=b'X'*70000,headers={'content-type':'application/json'})
    assert response.status_code==413


def test_workbook_contains_editable_assumptions_live_formulas_and_literal_notes():
    result=model();result['assumptions']['note']='=HYPERLINK("https://example.com","not a formula")'
    book=load_workbook(export_workbook(result),data_only=False)
    assert book.sheetnames==['Valuation','Assumptions','Forecast','Actuals','Checks','ReadMe']
    assert book['Assumptions']['E8'].value==0
    assert book['Forecast']['E9'].data_type=='f'
    assert book['Valuation']['D8'].value=="='Forecast'!D57"
    assert book['Forecast']['D57'].data_type=='f'
    assert all(cell.data_type!='f' for row in book['ReadMe'] for cell in row)
    for name in ['Valuation','Assumptions','Forecast']:
        for row in book[name]:
            for cell in row:
                if cell.data_type=='f':assert 'Checks!' not in cell.value and "'Checks'!" not in cell.value
    assert book.calculation.fullCalcOnLoad


def test_excel_download_recalculates_from_server_inputs(monkeypatch):
    monkeypatch.setattr(main,'load_model_baseline',lambda symbol: baseline())
    response=TestClient(main.app).post('/api/research/export-model',json=request())
    assert response.status_code==200
    assert response.headers['content-type'].startswith('application/vnd.openxmlformats')
    assert load_workbook(BytesIO(response.content))['Actuals']['D8'].value==100
