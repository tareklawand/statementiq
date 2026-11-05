/* Public, stateless forecast tools. No account and no public storage of assumptions. */
const ForecastWorkspace = (() => {
    const $ = id => document.getElementById(id);
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const definitions = [
        ['revenue_growth','Revenue growth','rate'],['gross_margin','Gross margin','rate'],['operating_margin','Operating margin after stock compensation','rate'],
        ['tax_rate','Tax rate','rate'],['capex_rate','Capital expenditure / revenue','rate'],['da_rate','D&A / revenue','rate'],['sbc_rate','Stock compensation / revenue','rate'],
        ['receivables_days','Closing receivables days','days'],['inventory_days','Closing inventory days','days'],['payables_days','Closing payables days','days'],
        ['interest_rate','Interest rate on average debt','rate'],['debt_draw','New debt','money'],['debt_repayment','Debt repayment','money'],
        ['equity_issuance','Equity proceeds','money'],['dividends','Dividends','money'],['buybacks','Share repurchases','money']
    ];
    const valuationDefinitions = [['wacc','WACC','rate'],['terminal_growth','Terminal growth','rate'],['terminal_roic','Terminal ROIC','rate'],
        ['cash_in_bridge','Cash included in equity value','money'],['nonoperating_assets','Other nonoperating assets','money'],['other_claims','Other claims on firm value','money']];
    let symbol = null, baseline = null, result = null, submitted = null, revision = 0, controller = null;
    let years = Array.from({length:5}, () => Object.fromEntries(definitions.map(([key]) => [key,null])));
    let valuation = Object.fromEntries(valuationDefinitions.map(([key]) => [key,null]));
    const units = type => type === 'rate' ? '%' : type === 'money' ? 'millions' : 'days';
    const scale = type => type === 'rate' ? .01 : type === 'money' ? 1e6 : 1;
    const currentYear = () => Number($('modelYear').value);
    function invalidate() {
        result = submitted = null;
        $('downloadModelExcelBtn').disabled = $('downloadModelJsonBtn').disabled = true;
        $('modelResults').innerHTML = '';
    }
    function changedInputs() {
        revision++; controller?.abort(); invalidate(); $('runForecastBtn').disabled=false;
        $('modelStatus').textContent='Assumptions changed. Calculate again to update the results and downloads.';
    }
    function fields() {
        $('modelDriverFields').innerHTML = definitions.map(([key,label,type]) => `<label for="driver_${key}">${esc(label)}${type==='days'?'':` <small>${units(type)}</small>`}<input id="driver_${key}" data-driver="${key}" data-unit="${type}" type="number" step="any" required></label>`).join('');
        $('modelValuationFields').innerHTML = valuationDefinitions.map(([key,label,type]) => `<label for="value_${key}">${esc(label)} <small>${units(type)}</small><input id="value_${key}" data-valuation="${key}" data-unit="${type}" type="number" step="any" required></label>`).join('');
        populate();
    }
    function populate() {
        const show = (value,type) => value == null ? '' : Number((value / scale(type)).toPrecision(12));
        for (const [key,,type] of definitions) $(`driver_${key}`).value = show(years[currentYear()][key],type);
        for (const [key,,type] of valuationDefinitions) $(`value_${key}`).value = show(valuation[key],type);
    }
    async function loadBaseline() {
        if (!symbol) return;
        const token = ++revision;
        controller?.abort(); controller = new AbortController();
        baseline = null; invalidate(); $('forecastForm').hidden = true;
        $('runForecastBtn').disabled=false;
        $('modelBaseline').innerHTML = ''; $('modelStatus').textContent = 'Retrieving aligned latest reported statements…';
        $('loadModelBaselineBtn').disabled = true;
        try {
            const response = await StatementIQRequests.requestJson(`/api/research/model-baseline?ticker=${encodeURIComponent(symbol)}`, {signal:controller.signal,maxAttempts:2,maxElapsedMs:120000,attemptTimeoutMs:90000});
            if (token !== revision) return;
            baseline = response;
            $('modelBaseline').innerHTML = `<div class="model-source"><strong>${esc(baseline.company_name)} · ${esc(baseline.currency || 'Currency unavailable')}</strong><p>Reported baseline and valuation date: ${esc(baseline.period || 'Unavailable')}. Income basis: ${esc(baseline.flow_basis?.replaceAll('_',' ') || 'Unavailable')}. Balance sheet: ${esc(baseline.balance_sheet_basis?.replaceAll('_',' ') || 'Unavailable')}. The five forecast periods use annual anniversaries of this date, not confirmed future fiscal closing dates.</p><details><summary>Source inputs and model scope</summary><p>${esc(baseline.scope)}</p><p>Other claims and cash treated as nonoperating are analyst assumptions. This model uses reported book borrowings in the equity bridge.</p><ul>${Object.entries(baseline.provenance).map(([key,p]) => `<li>${esc(key.replaceAll('_',' '))}: ${esc(p.row || 'Unavailable')} · ${esc(p.provider || 'Source unavailable')} · ${esc(p.period || '')}</li>`).join('')}</ul></details></div>`;
            if (baseline.status !== 'ready') {
                $('modelStatus').textContent = 'This baseline cannot support the operating-company model: ' + baseline.missing.join('; ');
                return;
            }
            $('forecastForm').hidden = false; fields();
            $('modelStatus').textContent = 'Reported baseline loaded. Enter all five years of assumptions and the DCF inputs. No forecast values have been invented.';
        } catch (error) {
            if (token === revision && error.name !== 'AbortError') $('modelStatus').textContent = 'The reported baseline is unavailable. Try again shortly.';
        } finally { if (token === revision) $('loadModelBaselineBtn').disabled = false; }
    }
    function requestBody() {
        if (!baseline) throw new Error('Load the reported baseline first.');
        for (let index=0;index<5;index++) for (const [key,label] of definitions) if (!Number.isFinite(years[index][key])) throw new Error(`Year ${index+1}: enter ${label.toLowerCase()}.`);
        for (const [key,label] of valuationDefinitions) if (!Number.isFinite(valuation[key])) throw new Error(`Enter ${label.toLowerCase()}.`);
        return {symbol, baseline_sha256:baseline.input_sha256, years, valuation, note:$('modelRationale').value.trim()};
    }
    async function post(url, payload) {
        const response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(payload),signal:controller.signal,cache:'no-store'});
        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(typeof detail.detail === 'string' ? detail.detail : 'The model request could not be completed. Check the inputs and try again.');
        }
        return response;
    }
    async function calculate(event) {
        event.preventDefault();
        let payload;
        try { payload = JSON.parse(JSON.stringify(requestBody())); } catch(error) { $('modelStatus').textContent=error.message; return; }
        const token=++revision;
        controller?.abort(); controller=new AbortController(); invalidate();
        $('runForecastBtn').disabled=true; $('modelStatus').textContent='Calculating forecast statements, cash reconciliation and DCF…';
        const timer=setTimeout(() => controller.abort(),120000);
        try {
            const response=await post('/api/research/forecast',payload);
            const calculated=await response.json();
            if(token!==revision)return;
            result=calculated; submitted=payload; render();
            $('downloadModelExcelBtn').disabled=$('downloadModelJsonBtn').disabled=false;
            $('modelStatus').textContent=result.dcf.status==='ready' ? 'Forecast calculated. Cash and balance-sheet checks reconcile. Review your assumptions and model scope before using the valuation.' : result.dcf.reason;
        } catch(error) { if(token===revision) $('modelStatus').textContent=error.name==='AbortError' ? 'Calculation timed out. Try again shortly.' : error.message; }
        finally { clearTimeout(timer); if(token===revision)$('runForecastBtn').disabled=false; }
    }
    function money(value) {
        return typeof value==='number'&&Number.isFinite(value) ? (value/1e6).toLocaleString('en-US',{maximumFractionDigits:2}) : 'N/A';
    }
    function render() {
        const dcf=result.dcf;
        $('modelResults').innerHTML=`<section class="research-section"><h3>DCF at ${esc(dcf.valuation_date)}</h3><p>Figures in ${esc(baseline.currency)} millions. Constant user-entered WACC, annual end-year discounting and a terminal growth / ROIC reinvestment model.</p><div class="model-value-grid">${[['Enterprise value',dcf.enterprise_value],['Equity value',dcf.equity_value]].map(([label,value])=>`<article><span>${label}</span><strong>${money(value)}</strong></article>`).join('')}<article><span>Value per reported common share</span><strong>${typeof dcf.value_per_share==='number' ? `${esc(baseline.currency)} ${dcf.value_per_share.toFixed(2)}` : 'N/A'}</strong><small>At baseline date, not today's quote date.</small></article></div>${dcf.reason?`<p>${esc(dcf.reason)}</p>`:''}<p>${esc(dcf.per_share_scope)}</p><p>Terminal reinvestment rate: ${(dcf.terminal_reinvestment_rate*100).toFixed(2)}%. Terminal NOPAT: ${money(dcf.terminal_nopat)}. Terminal free cash flow: ${money(dcf.terminal_fcff)}.</p></section>
        <section class="research-section"><h3>Linked forecast statements</h3><p>Forecasts use your assumptions. Negative cash identifies a funding gap; no financing has been added automatically.</p><div class="analysis-table-scroll"><table class="financial-table"><thead><tr><th>Forecast line (${esc(baseline.currency)} millions)</th>${result.forecasts.map(row=>`<th>Year ${row.year}<small>${esc(row.period)}</small></th>`).join('')}</tr></thead><tbody>${[
            ['Revenue','revenue'],['Gross profit','gross_profit'],['Operating income','operating_income'],['Interest expense','interest_expense'],['Tax provision','tax_provision'],['Net income','net_income'],
            ['Operating cash flow','operating_cash_flow'],['Investing cash flow','investing_cash_flow'],['Financing cash flow','financing_cash_flow'],['Ending cash / funding deficit','cash'],
            ['Assets','assets'],['Liabilities','liabilities'],['Equity','equity'],['Borrowings','debt'],['Unlevered free cash flow','fcff'],['Cash reconciliation difference','cash_difference'],['Balance-sheet difference','balance_difference']
        ].map(([label,key])=>`<tr><td>${label}</td>${result.forecasts.map(row=>`<td>${key.endsWith('difference') ? (Math.abs(row[key])<.005?'0.00':row[key].toFixed(2)) : money(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p>Reconciliation differences are shown in full currency units. Other figures are in millions.</p>${result.warnings.map(warning=>`<p>${esc(warning)}</p>`).join('')}<details><summary>Model limitations and sources</summary><p>${esc(result.scope)}</p>${result.methodology_sources.map(url=>`<p><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a></p>`).join('')}</details></section>`;
    }
    function download(blob,name) { const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
    async function exportExcel() {
        if(!submitted)return;
        const token=++revision, payload=submitted;
        controller?.abort();controller=new AbortController();$('downloadModelExcelBtn').disabled=true;
        const timer=setTimeout(()=>controller.abort(),120000);
        try {const response=await post('/api/research/export-model',payload); const blob=await response.blob();if(token===revision)download(blob,`${symbol}_forecast_DCF.xlsx`);}
        catch(error) {if(token===revision)$('modelStatus').textContent=error.message;}
        finally {clearTimeout(timer);if(token===revision&&result)$('downloadModelExcelBtn').disabled=false;}
    }
    document.addEventListener('input',event=>{
        const target=event.target;
        if(target.dataset.driver||target.dataset.valuation){
            const value=target.value===''?null:Number(target.value)*scale(target.dataset.unit);
            if(target.dataset.driver)years[currentYear()][target.dataset.driver]=value;
            else valuation[target.dataset.valuation]=value;
            changedInputs();
        }else if(target.id==='modelRationale')changedInputs();
    });
    document.addEventListener('change',event=>{if(event.target.id==='modelYear')populate();});
    document.addEventListener('submit',event=>{if(event.target.id==='forecastForm')void calculate(event);});
    document.addEventListener('click',event=>{
        const id=event.target.closest('button')?.id;
        if(id==='loadModelBaselineBtn')void loadBaseline();
        if(id==='copyHistoricalBtn'&&baseline){for(const [key] of definitions)if(baseline.historical_drivers[key]!=null)years[currentYear()][key]=baseline.historical_drivers[key];populate();changedInputs();}
        if(id==='zeroFinancingBtn'){for(const key of ['debt_draw','debt_repayment','equity_issuance','dividends','buybacks'])years[currentYear()][key]=0;populate();changedInputs();}
        if(id==='copyModelYearBtn'){years=years.map(()=>({...years[currentYear()]}));populate();changedInputs();$('modelStatus').textContent='Selected-year values applied to all five forecast years. Review the assumptions for each year.';}
        if(id==='useReportedCashBtn'&&baseline){valuation.cash_in_bridge=baseline.values.cash;populate();changedInputs();}
        if(id==='downloadModelJsonBtn'&&result)download(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),`${symbol}_forecast_DCF.json`);
        if(id==='downloadModelExcelBtn')void exportExcel();
    });
    return {open(){if(symbol&&!baseline&&!$('loadModelBaselineBtn').disabled)void loadBaseline();},setCompany(payload,openWhenReady=false){
        const changed=symbol!==payload.symbol;symbol=payload.symbol;revision++;controller?.abort();baseline=null;invalidate();
        if(changed){years=Array.from({length:5},()=>Object.fromEntries(definitions.map(([key])=>[key,null])));valuation=Object.fromEntries(valuationDefinitions.map(([key])=>[key,null]));$('modelRationale').value='';}
        $('forecastForm').hidden=true;$('modelBaseline').innerHTML='';$('loadModelBaselineBtn').disabled=false;$('runForecastBtn').disabled=false;
        $('modelStatus').textContent=`Load ${symbol}'s reported annual/TTM baseline to start. Forecasts are never used as reported actuals.`;
        if(openWhenReady)void loadBaseline();
    }};
})();
