"""Portable Excel export for the Python service; local QA independently recalculates formulas."""
from copy import copy
from datetime import date
from io import BytesIO
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

from forecast_model import DRIVERS, FIELDS

MONEY = '#,##0.0,,;(#,##0.0,,);"—"'
NUMBER = '#,##0.00;(#,##0.00);"—"'
DIFFERENCE = '#,##0.00;(#,##0.00);0.00'
RATE = '0.0%;(0.0%);"—"'
DARK, OLIVE, CREAM, MUTED = '1D241B', '536D32', 'EFECE2', '686D64'
INPUT, LINK = '2056A5', '197247'
LABELS = {
    'revenue_growth':'Revenue growth', 'gross_margin':'Gross margin', 'operating_margin':'Operating margin after SBC',
    'tax_rate':'Tax rate', 'capex_rate':'Capex / revenue', 'da_rate':'D&A / revenue', 'sbc_rate':'SBC / revenue',
    'receivables_days':'Closing receivables days', 'inventory_days':'Closing inventory days', 'payables_days':'Closing payables days',
    'interest_rate':'Interest rate on average debt', 'debt_draw':'New debt', 'debt_repayment':'Debt repayment',
    'equity_issuance':'Equity proceeds', 'dividends':'Dividends', 'buybacks':'Share repurchases'}
ROWS = {'revenue':9,'cogs':10,'gross_profit':11,'operating_expenses':12,'operating_income':13,'interest_expense':14,
    'pretax_income':15,'tax_provision':16,'net_income':17,'da':19,'sbc':20,'capex':21,'receivables':23,
    'inventory':24,'payables':25,'change_working_capital':26,'operating_cash_flow':28,'investing_cash_flow':29,
    'financing_cash_flow':30,'cash':32,'debt':33,'other_noncash_assets':34,'other_liabilities':35,'equity':36,
    'assets':37,'liabilities':38,'nopat':40,'fcff':41,'discount_factor':42,'present_value_fcff':43,
    'funding_gap':45,'balance_difference':46,'cash_difference':47}
ACTUAL_KEYS = tuple(FIELDS) + ('prior_revenue','prior_debt')
ACTUAL_ROWS = {key:8+i for i,key in enumerate(ACTUAL_KEYS)}


def text(cell, value):
    cell.value = str(value)
    cell.data_type = 's'  # user notes/company labels never become Excel formulas


def export_workbook(result):
    wb=Workbook(); wb.remove(wb.active)
    sheets={name:wb.create_sheet(name) for name in ('Valuation','Assumptions','Forecast','Actuals','Checks','ReadMe')}
    base=result['baseline']; values=base['values']; assumption=result['assumptions']
    for name,sheet in sheets.items():
        sheet.sheet_view.showGridLines=False
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.orientation='landscape'; sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth=1; sheet.page_setup.fitToHeight=0
        sheet.column_dimensions['A'].width=2; sheet.column_dimensions['B'].width=2
        sheet.column_dimensions['C'].width=36
        for col in 'DEFGHI':sheet.column_dimensions[col].width=19
        for row in sheet.iter_rows(min_row=1,max_row=85,min_col=3,max_col=9):
            for cell in row:cell.font=Font(name='Arial',size=10,color=DARK);cell.alignment=Alignment(vertical='center')
        for row in range(1,86):sheet.row_dimensions[row].height=21
        text(sheet['C2'],f"{base['symbol']} {name}");sheet['C2'].font=Font(name='Arial',size=14,bold=True,color=DARK)
        sheet['C3']=f"{base['currency']} millions unless otherwise indicated"
        sheet['C3'].font=Font(name='Arial',size=10,italic=True,color=MUTED)
        sheet.print_options.horizontalCentered=True
        sheet.print_area='C2:I82'
        if name not in ('Valuation','ReadMe'):sheet.freeze_panes='E8'
        sheet.sheet_properties.tabColor=DARK if name=='Valuation' else OLIVE if name=='Assumptions' else 'E9DFC8' if name=='Actuals' else None
    def formula(sheet,address,expression):
        cell=sheet[address];cell.value='='+expression
        cell.font=Font(name='Arial',size=10,color=LINK if "'" in expression and sheet.title not in ('Valuation','Checks') else DARK)
        cell.number_format=MONEY
    def header(sheet,row,labels):
        for col,label in enumerate(labels,3):
            cell=sheet.cell(row,col,label);cell.fill=PatternFill('solid',fgColor=DARK)
            cell.font=Font(name='Arial',size=10,bold=True,color='FFFFFF');cell.alignment=Alignment(horizontal='center',vertical='center')
        sheet.row_dimensions[row].height=28
    actual=sheets['Actuals']
    header(actual,7,['Source input','Reported value','Period','Source row','Provider','Filing / provider URL','Source facts'])
    for key,row in ACTUAL_ROWS.items():
        p=base['provenance'][key]
        text(actual.cell(row,3),key.replace('_',' ').capitalize())
        actual.cell(row,4,values[key] if values[key] is not None else 'n.a.').number_format=NUMBER if key=='shares' else MONEY
        actual.cell(row,5,date.fromisoformat(p['period']) if p.get('period') else 'n.a.').number_format='yyyy-mm-dd'
        text(actual.cell(row,6),p.get('row') or 'Unavailable');text(actual.cell(row,7),p.get('provider') or 'Unavailable')
        sources=(p.get('sec_facts') or {}).get('sources') or []
        accession=sources[0].get('accession_number') if sources else None
        cik=(base.get('latest_filing') or {}).get('cik')
        url=(f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/' if cik and accession else f'https://finance.yahoo.com/quote/{base["symbol"]}/financials/')
        text(actual.cell(row,8),'Open source');actual.cell(row,8).hyperlink=url;actual.cell(row,8).style='Hyperlink'
        text(actual.cell(row,9),'; '.join(f"{source.get('tag')} × {source.get('coefficient',1)}" for source in sources) or 'Provider source row')
        for col in (6,7,9):actual.cell(row,col).alignment=Alignment(wrap_text=True,vertical='center')
        actual.row_dimensions[row].height=45
    actual.column_dimensions['F'].width=35;actual.column_dimensions['G'].width=24
    actual.column_dimensions['H'].width=48;actual.column_dimensions['I'].width=45
    actual['C34']='Original baseline input SHA-256';text(actual['D34'],base['input_sha256'])
    actual['C35']='Download is a frozen observation. Reload StatementIQ to obtain newly reported actuals.'
    actual.print_area='C2:I35'
    ass=sheets['Assumptions']; forecast=sheets['Forecast']; valuation=sheets['Valuation']; checks=sheets['Checks']
    dates=[date.fromisoformat(base['period'])]+[date.fromisoformat(y['period']) for y in result['forecasts']]
    for sheet in (ass,forecast,checks):
        header(sheet,7,['Metric']+dates)
        for col in range(4,10):sheet.cell(7,col).number_format='yyyy-mm-dd'
    for i,key in enumerate(DRIVERS,8):
        ass.cell(i,3,LABELS[key]);formula(ass,f'D{i}',f"'Forecast'!D{65+i-8}")
        for index,col in enumerate('EFGHI'):
            cell=ass[f'{col}{i}'];cell.value=assumption['years'][index][key]
            cell.font=Font(name='Arial',size=10,color=INPUT)
            cell.fill=PatternFill('solid',fgColor='F5F1D8')
            cell.number_format=RATE if i in tuple(range(8,15))+(18,) else NUMBER if i in (15,16,17) else MONEY
        ass[f'D{i}'].number_format=ass[f'E{i}'].number_format
    ass['C26']='Year assumptions valid (1 / 0)'
    for col in 'EFGHI':formula(ass,f'{col}26',f'IF(COUNT({col}8:{col}23)=16,IF(AND({col}8>-1,{col}9<=1,{col}10<={col}9,{col}11>=0,{col}11<=1,MIN({col}11:{col}23)>=0,{col}13+{col}14<=1-{col}10+1E-12),1,0),0)');ass[f'{col}26'].number_format='0'
    global_keys=('wacc','terminal_growth','terminal_roic','cash_in_bridge','nonoperating_assets','other_claims')
    for row,key in enumerate(global_keys,30):
        ass.cell(row,3,key.replace('_',' ').capitalize());ass.cell(row,4,assumption['valuation'][key])
        ass.cell(row,4).font=Font(name='Arial',size=10,color=INPUT);ass.cell(row,4).fill=PatternFill('solid',fgColor='F5F1D8')
        ass.cell(row,4).number_format=RATE if row<=32 else MONEY
    cash_ref=f"'Actuals'!D{ACTUAL_ROWS['cash']}"
    formula(ass,'D38',f'IF(COUNT(D30:D35)=6,IF(AND(D30>0,D31>-1,D31<D30,D32>MAX(0,D31),D33>=0,D33<={cash_ref},D34>=0,D35>=0),1,0),0)')
    ass['C38']='Valuation inputs valid (1 / 0)';ass['D38'].number_format='0'
    ass['C40']='Blue: editable assumptions. Green: links. n.a.: missing or invalid input.'
    ass['C41']='Tax applies only to positive pretax income. WACC is constant across forecast years.'
    ass['C42']='Forecasts have no NOL, OCI, FX, acquisition or minority-interest schedules.'
    ass.print_area='C2:I42'
    for key,row in ROWS.items():
        label={'cogs':'Cost of revenue','da':'D&A','sbc':'Stock compensation','nopat':'NOPAT','fcff':'Unlevered free cash flow','present_value_fcff':'Present value of FCFF'}.get(key,key.replace('_',' ').capitalize())
        text(forecast.cell(row,3),label)
        if key in ACTUAL_ROWS:formula(forecast,f'D{row}',f"IF(ISNUMBER('Actuals'!D{ACTUAL_ROWS[key]}),'Actuals'!D{ACTUAL_ROWS[key]},\"n.a.\")")
        else:forecast.cell(row,4,'n.a.')
    formula(forecast,'D10','IF(COUNT(D9,D11)=2,D9-D11,"n.a.")')
    formula(forecast,'D12','IF(COUNT(D11,D13)=2,D11-D13,"n.a.")')
    formula(forecast,'D21',f'IF(ISNUMBER(\'Actuals\'!D{ACTUAL_ROWS["capital_expenditure"]}),-\'Actuals\'!D{ACTUAL_ROWS["capital_expenditure"]},"n.a.")')
    formula(forecast,'D34','IF(COUNT(D37,D32,D23,D24)=4,D37-D32-D23-D24,"n.a.")')
    formula(forecast,'D35','IF(COUNT(D38,D33,D25)=3,D38-D33-D25,"n.a.")')
    formula(forecast,'D6','IF(COUNT(D9,D32:D38,D23:D25)=11,IF(AND(D9>0,ABS(D37-D38-D36)<=1),1,0),0)')
    forecast['C6']='Model inputs valid (1 / 0)';forecast['D6'].number_format='0'
    for index,col in enumerate('EFGHI',1):
        prev=get_column_letter(4+index-1);a=lambda row:f"'Assumptions'!{col}{row}"
        formula(forecast,f'{col}5',f'IF(AND({a(26)}=1,ISNUMBER({prev}9)),{prev}9*(1+{a(8)}),"n.a.")')
        formula(forecast,f'{col}6',f'IF(AND({a(26)}=1,{prev}6=1,COUNT({prev}9,{prev}32:{prev}36,{prev}23:{prev}25)=9),IF(AND({prev}33+{a(19)}-{a(20)}>=0,{prev}34+{col}5*({a(12)}-{a(13)})>=-1),1,0),0)')
        forecast[f'{col}6'].number_format='0'
        expressions={9:f'{col}5',10:f'{col}9-{col}11',11:f'{col}9*{a(9)}',12:f'{col}11-{col}13',13:f'{col}9*{a(10)}',
            14:f'({prev}33+{col}33)/2*{a(18)}',15:f'{col}13-{col}14',16:f'MAX({col}15,0)*{a(11)}',17:f'{col}15-{col}16',
            19:f'{col}9*{a(13)}',20:f'{col}9*{a(14)}',21:f'{col}9*{a(12)}',23:f'{col}9/365*{a(15)}',24:f'{col}10/365*{a(16)}',25:f'{col}10/365*{a(17)}',
            26:f'{col}23-{prev}23+{col}24-{prev}24-{col}25+{prev}25',28:f'SUM({col}17,{col}19:{col}20)-{col}26',29:f'-{col}21',
            30:f'{a(19)}-{a(20)}+{a(21)}-{a(22)}-{a(23)}',32:f'SUM({prev}32,{col}28:{col}30)',33:f'{prev}33+{a(19)}-{a(20)}',
            34:f'{prev}34+{col}21-{col}19',35:f'{prev}35',36:f'{prev}36+{col}17+{col}20+{a(21)}-{a(22)}-{a(23)}',
            37:f'SUM({col}32,{col}23:{col}24,{col}34)',38:f'SUM({col}33,{col}25,{col}35)',40:f'{col}13-MAX({col}13,0)*{a(11)}',41:f'{col}40+{col}19-{col}21-{col}26',
            42:f'(1+\'Assumptions\'!$D$30)^{index}',43:f'{col}41/{col}42',45:f'MAX(-{col}32,0)',46:f'{col}37-{col}38-{col}36',47:f'{col}32-{prev}32-SUM({col}28:{col}30)'}
        for row,expression in expressions.items():formula(forecast,f'{col}{row}',f'IF({col}6=1,{expression},"n.a.")')
        formula(forecast,f'{col}42',f'IF(AND({col}6=1,\'Assumptions\'!$D$38=1),(1+\'Assumptions\'!$D$30)^{index},"n.a.")')
        formula(forecast,f'{col}43',f'IF(AND({col}6=1,ISNUMBER({col}42)),{col}41/{col}42,"n.a.")')
        forecast[f'{col}42'].number_format='0.0000';forecast[f'{col}46'].number_format=forecast[f'{col}47'].number_format=DIFFERENCE
    dcf={52:'IF(AND(\'Assumptions\'!D38=1,ISNUMBER(I40)),I40*(1+\'Assumptions\'!D31),"n.a.")',
        53:'IF(\'Assumptions\'!D38=1,\'Assumptions\'!D31/\'Assumptions\'!D32,"n.a.")',
        54:'IF(COUNT(D52:D53)=2,D52*(1-D53),"n.a.")',
        55:'IF(AND(ISNUMBER(D54),COUNT(E45:I45)=5,\'Assumptions\'!D38=1),IF(AND(D54>0,MAX(E45:I45)=0),D54/(\'Assumptions\'!D30-\'Assumptions\'!D31),"n.a."),"n.a.")',
        56:'IF(COUNT(D55,I42)=2,D55/I42,"n.a.")',57:'IF(COUNT(E43:I43,D56)=6,SUM(E43:I43,D56),"n.a.")',
        58:'IF(ISNUMBER(D57),D57+\'Assumptions\'!D33+\'Assumptions\'!D34-D33-\'Assumptions\'!D35,"n.a.")',
        59:f'IF(COUNT(D58,\'Actuals\'!D{ACTUAL_ROWS["shares"]})=2,IF(AND(D58>=0,\'Actuals\'!D{ACTUAL_ROWS["shares"]}>0),D58/\'Actuals\'!D{ACTUAL_ROWS["shares"]},"n.a."),"n.a.")'}
    names=('Terminal NOPAT','Terminal reinvestment rate','Terminal FCFF','Terminal value','Present value terminal','Enterprise value','Equity value','Value per common share')
    for row,label in enumerate(names,52):forecast.cell(row,3,label);formula(forecast,f'D{row}',dcf[row])
    forecast['D53'].number_format=RATE;forecast['D59'].number_format=NUMBER
    historical={
        'revenue_growth':f'IF(COUNT(D9,\'Actuals\'!D{ACTUAL_ROWS["prior_revenue"]})=2,IF(\'Actuals\'!D{ACTUAL_ROWS["prior_revenue"]}>0,D9/\'Actuals\'!D{ACTUAL_ROWS["prior_revenue"]}-1,"n.a."),"n.a.")',
        'gross_margin':'IF(COUNT(D11,D9)=2,IF(D9>0,D11/D9,"n.a."),"n.a.")',
        'operating_margin':'IF(COUNT(D13,D9)=2,IF(D9>0,D13/D9,"n.a."),"n.a.")',
        'da_rate':'IF(COUNT(D19,D9)=2,IF(D9>0,D19/D9,"n.a."),"n.a.")',
        'sbc_rate':'IF(COUNT(D20,D9)=2,IF(D9>0,D20/D9,"n.a."),"n.a.")',
        'capex_rate':'IF(COUNT(D21,D9)=2,IF(AND(D9>0,D21>=0),D21/D9,"n.a."),"n.a.")',
        'tax_rate':'IF(COUNT(D15:D16)=2,IF(AND(D15>0,D16>=0,D16<=D15),D16/D15,"n.a."),"n.a.")',
        'receivables_days':'IF(COUNT(D23,D9)=2,IF(D9>0,365*D23/D9,"n.a."),"n.a.")',
        'inventory_days':'IF(COUNT(D24,D10)=2,IF(D10>0,365*D24/D10,"n.a."),"n.a.")',
        'payables_days':'IF(COUNT(D25,D10)=2,IF(D10>0,365*D25/D10,"n.a."),"n.a.")',
        'interest_rate':f'IF(COUNT(D14,D33,\'Actuals\'!D{ACTUAL_ROWS["prior_debt"]})=3,IF(AND(D14>=0,D33+\'Actuals\'!D{ACTUAL_ROWS["prior_debt"]}>0),D14/((D33+\'Actuals\'!D{ACTUAL_ROWS["prior_debt"]})/2),"n.a."),"n.a.")'}
    for i,key in enumerate(DRIVERS,65):
        forecast.cell(i,3,'Historical '+LABELS[key])
        # Calibration is explicitly dated source analysis, not a forecast assumption.
        if key in historical:formula(forecast,f'D{i}',historical[key])
        else:forecast.cell(i,4,'n.a.')
        forecast.cell(i,4).number_format=ass.cell(8+i-65,4).number_format
    forecast.row_dimensions[5].hidden=True
    header(valuation,6,['Valuation at reporting date',date.fromisoformat(base['period'])])
    valuation['D6'].number_format='yyyy-mm-dd'
    for row,label,ref in ((8,'Enterprise value',57),(9,'Equity value',58),(10,'Value per common share',59),(11,'Terminal value',55)):
        valuation.cell(row,3,label);formula(valuation,f'D{row}',f"'Forecast'!D{ref}")
    valuation['D10'].number_format=NUMBER
    valuation['C13']='Annual end-year discounting. Values are at the reporting baseline date, not today.'
    header(valuation,16,['Forecast metric']+dates)
    for col in range(4,10):valuation.cell(16,col).number_format='yyyy-mm-dd'
    for row,(key,src) in enumerate((('Revenue',9),('Operating income',13),('Net income',17),('Operating cash flow',28),('Ending cash / funding deficit',32),('Borrowings',33),('Assets',37),('Liabilities',38),('Equity',36),('Unlevered free cash flow',41)),18):
        valuation.cell(row,3,key)
        for col in 'DEFGHI':formula(valuation,f'{col}{row}',f"'Forecast'!{col}{src}")
    text(valuation['C2'],f"{base['symbol']} DCF valuation")
    text(valuation['C4'],base['company_name'])
    for cell in valuation['C2:I2'][0]:cell.border=Border(bottom=Side(style='thin',color=OLIVE))
    for row in (8,9,10,11):
        valuation[f'D{row}'].font=Font(name='Arial',size=14 if row==10 else 10,bold=True,color=OLIVE if row==10 else DARK)
        valuation[f'C{row}'].font=Font(name='Arial',size=10,bold=row==10,color=DARK)
    for col in 'FGHI':
        valuation[f'{col}6'].fill=PatternFill('solid',fgColor=DARK)
        valuation[f'{col}6'].font=Font(name='Arial',size=10,bold=True,color='FFFFFF')
    valuation['F6']='Enterprise to equity'
    bridge=[('PV of forecast cash flows',"IF(COUNT('Forecast'!E43:I43)=5,SUM('Forecast'!E43:I43),\"n.a.\")"),
        ('PV of terminal value',"'Forecast'!D56"),('Enterprise value',"'Forecast'!D57"),
        ('Cash included',"'Assumptions'!D33"),('Other nonoperating assets',"'Assumptions'!D34"),
        ('Less: borrowings',"'Forecast'!D33"),('Less: other claims',"'Assumptions'!D35"),('Equity value',"'Forecast'!D58")]
    for row,(label,expression) in enumerate(bridge,7):
        valuation[f'F{row}']=label;formula(valuation,f'I{row}',expression)
        if row in (9,14):
            for col in 'FGHI':valuation[f'{col}{row}'].border=Border(top=Side(style='thin',color='B9BDAF'))
            valuation[f'F{row}'].font=valuation[f'I{row}'].font=Font(name='Arial',size=10,bold=True,color=DARK)
    valuation['C29']='Valuation assumptions'
    for cell in valuation['C29:I29'][0]:cell.fill=PatternFill('solid',fgColor=CREAM)
    for label,address,source in [('WACC','C30',"'Assumptions'!D30"),('Terminal ROIC','C31',"'Assumptions'!D32"),
                                 ('Terminal growth','F30',"'Assumptions'!D31"),('Terminal reinvestment','F31',"'Forecast'!D53")]:
        valuation[address]=label
        target=('D' if address.startswith('C') else 'I')+address[1:]
        formula(valuation,target,source);valuation[target].number_format=RATE
    valuation['C33']='Valuation uses reported point-in-time common shares. Forecast years follow annual anniversaries of the baseline date.'
    valuation['C35']='n.a.: missing or invalid inputs, an unfunded cash position, or no positive terminal cash flow.'
    valuation.print_area='C2:I35'
    for row,label,ref in ((9,'Cash rollforward difference',47),(10,'Balance-sheet difference',46),(11,'Unfunded cash position',45)):
        checks.cell(row,3,label)
        for col in 'EFGHI':formula(checks,f'{col}{row}',f"'Forecast'!{col}{ref}");checks[f'{col}{row}'].number_format=DIFFERENCE
    checks['C13']='Differences are full currency units. Positive funding gaps require explicit financing.'
    checks.conditional_formatting.add('E9:I11',CellIsRule(operator='greaterThan',formula=['1'],fill=PatternFill('solid',fgColor='FBE1DF'),font=Font(color='B42318',bold=True)))
    checks.conditional_formatting.add('E9:I10',CellIsRule(operator='lessThan',formula=['-1'],fill=PatternFill('solid',fgColor='FBE1DF'),font=Font(color='B42318',bold=True)))
    checks.print_area='C2:I13'
    readme=sheets['ReadMe'];readme.column_dimensions['C'].width=110
    notes=[f"Valuation and forecast baseline: {base['period']}. All source amounts are full currency units; display formats scale monetary values to millions.",
        'Edit blue cells on Assumptions. Every forecast year has its own dated inputs. Reported Actuals remain separate. This export is frozen and does not refresh filings by itself.',
        result['scope'], 'WACC is constant. Terminal FCFF is normalized NOPAT times (1 − terminal growth / terminal ROIC). Book borrowings are used in the equity bridge.',
        'Models with cash funding gaps do not produce a going-concern valuation. No debt plug is inserted. Missing point-in-time common shares leave the per-share result unavailable.',
        'Formulas recalculate in Excel when opened. Spreadsheet checks have been compared with the server model; this is not independent financial validation.',
        'Assumptions rationale: '+assumption['note'], 'Model version: '+result['model_version'], 'Model code SHA-256: '+result['model_code_sha256'],
        'Methodology: '+result['methodology_sources'][0], 'Terminal reinvestment: '+result['methodology_sources'][1]]
    for row,note in enumerate(notes,5):text(readme.cell(row,3),note);readme.cell(row,3).alignment=Alignment(wrap_text=True,vertical='top');readme.row_dimensions[row].height=65 if len(note)>250 else 42
    readme.print_area='C2:C15'
    # Template styling leaves all reported values and model formulas intact.
    for sheet in sheets.values():
        sheet.sheet_view.zoomScale=90
        for row in sheet:
            for cell in row:
                if cell.row not in (6,7) and cell.value is not None and (isinstance(cell.value,(int,float,date)) or cell.data_type=='f' or cell.value=='n.a.'):
                    cell.alignment=Alignment(horizontal='right',vertical='center',wrap_text=cell.alignment.wrap_text)
        if sheet.title not in ('Valuation','ReadMe'):sheet.print_title_rows='7:7'
    for row,label in [(18,'Noncash charges and reinvestment'),(22,'Working capital'),(27,'Cash flow'),(31,'Balance sheet'),(39,'Unlevered cash flow'),(44,'Reconciliation')]:
        forecast.cell(row,3,label)
        for cell in forecast[f'C{row}:I{row}'][0]:
            cell.fill=PatternFill('solid',fgColor=CREAM);cell.font=Font(name='Arial',size=10,bold=True,color=DARK)
    for sheet,rows in [(forecast,(13,17,28,32,37,38,41,43)),(valuation,(19,21,22,27))]:
        for row in rows:
            for cell in sheet[f'C{row}:I{row}'][0]:
                cell.border=Border(top=Side(style='hair',color='B9BDAF'))
                existing=copy(cell.font);existing.bold=True;cell.font=existing
    for row in range(8,19):
        for cell in ass[f'C{row}:I{row}'][0]:
            existing=copy(cell.font);existing.italic=True;cell.font=existing
    for sheet,row in [(valuation,17),(forecast,8),(ass,6)]:
        for col in 'DEFGHI':
            sheet[f'{col}{row}']='Reported' if col=='D' else 'Forecast'
            sheet[f'{col}{row}'].font=Font(name='Arial',size=10,italic=True,color=MUTED)
            sheet[f'{col}{row}'].alignment=Alignment(horizontal='center',vertical='center')
    readme.sheet_properties.tabColor='8C9383'
    wb.calculation.fullCalcOnLoad=True;wb.calculation.forceFullCalc=True;wb.calculation.calcMode='auto'
    output=BytesIO();wb.save(output);output.seek(0);return output
