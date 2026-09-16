// Reference exporter. Input contains submitted artifacts, not evaluator answers.
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: professional_workbook.mjs submission.json output-directory');
const submission = JSON.parse(await fs.readFile(input, 'utf8'));
const artifacts = submission.artifacts;
const model = artifacts.integrated_recovery_model.content;
const brief = artifacts.executive_decision_brief.content;
const schedule = artifacts.customer_commitment_schedule.content;
const impact = model.financial_impact;
const workbook = Workbook.create();
const financial = workbook.worksheets.add('Financial review');
const customer = workbook.worksheets.add('Customer schedule');
const money = '#,##0.00;(#,##0.00);"-"';
for (const sheet of [financial, customer]) {
  sheet.showGridLines = false;
  sheet.getRange('A1:H30').format.font = {name:'Arial',size:10};
  sheet.getRange('A1:H30').format.rowHeight = 22;
}
financial.getRange('A2').values = [['Operating reserve review']];
financial.getRange('A2').format.font = {bold:true,size:14};
financial.getRange('A3').values = [[`${model.case_id} / ${impact.period} / USD`]];
financial.getRange('A5:B5').values = [['Expense or recovery','USD']];
const components = [
 ['Disposal',impact.disposal_cost],['Inspection',impact.inspection_cost],
 ['Recovery production',impact.recovery_production_cost],['Supplier expedite',impact.supplier_expedite_cost],
 ['Premium freight',impact.premium_freight],['Customer penalties',impact.customer_penalty_exposure],
 ['Insurance receivable',-impact.insurance_recovery],
 ['Incremental AP expense',(impact.finance_bridge?.expense_cents ?? 0)/100],
];
financial.getRange('A6:B13').values = components;
financial.getRange('A15').values = [['Calculated reserve']];
financial.getRange('B15').formulas = [['=SUM(B6:B13)']];
financial.getRange('A17:B18').values = [
 ['Settled AP cash',(impact.finance_bridge?.settled_cash_cents ?? 0)/100],
 ['Remaining AP payable',null],
];
financial.getRange('B18').formulas = [['=B13-B17']];
financial.getRange('A20').values = [['Payments affect payable, not reserve expense.']];
financial.getRange('A22').values = [['Source: submitted integrated recovery model; citations below.']];
const cites = artifacts.integrated_recovery_model.citations.map(c=>`${c.file_id} / ${c.section_id} / v${c.version}`);
financial.getRange(`A24:A${23+cites.length}`).values = cites.map(c=>[c]);
financial.getRange('A5:A22').format.columnWidth = 55;
financial.getRange('B5:B18').format.columnWidth = 20;
financial.getRange('B6:B18').setNumberFormat(money);
financial.getRange('B6:B13').format.font.color = '#0000FF';
financial.getRange('B17').format.font.color = '#0000FF';
financial.getRange('A15:B15').format.font.bold = true;
financial.getRange('A5:B5').format = {fill:'#283747',font:{color:'#FFFFFF',bold:true}};
customer.getRange('A2').values = [['Customer commitments']];
customer.getRange('A2').format.font = {bold:true,size:14};
customer.getRange('A4:F4').values = [['Order','Requested','Committed','Shortfall','Arrival minute','Status']];
const rows = schedule.orders.map(o=>[o.order_id,o.requested_quantity,o.committed_quantity,null,o.latest_arrival_minute,o.status]);
customer.getRange(`A5:F${4+rows.length}`).values = rows;
customer.getRange(`D5:D${4+rows.length}`).formulas = rows.map((_,i)=>[`=B${i+5}-C${i+5}`]);
customer.getRange('A4:A12').format.columnWidth = 25;
customer.getRange('B4:E12').format.columnWidth = 17;
customer.getRange('F4:F12').format.columnWidth = 29;
customer.getRange('A4:F4').format = {fill:'#283747',font:{color:'#FFFFFF',bold:true}};
customer.getRange(`B5:E${4+rows.length}`).setNumberFormat('0');
workbook.recalculate();
const value = financial.getRange('B15').values[0][0];
if (Math.abs(value-impact.reserve_amount)>0.000001 || value !== brief.reserve_amount) throw new Error('Reserve reconciliation failed');
// Recalculation check: perturb and restore a source input before export.
financial.getRange('B6').values = [[components[0][1]+1]];
if (Math.abs(financial.getRange('B15').values[0][0]-value-1)>0.000001) throw new Error('Formula did not recalculate');
financial.getRange('B6').values = [[components[0][1]]];
workbook.recalculate();
await fs.mkdir(output,{recursive:true});
console.log((await workbook.inspect({kind:'table',range:'Financial review!A5:B18',include:'values,formulas',tableMaxRows:14,tableMaxCols:2})).ndjson);
console.log((await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20}})).ndjson);
for (const [sheet,range,file] of [['Financial review','A1:C20','financial.png'],['Customer schedule','A1:F10','customers.png']]) {
  const preview = await workbook.render({sheetName:sheet,range,scale:1.5,format:'png'});
  await fs.writeFile(`${output}/${file}`,new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(workbook)).save(`${output}/operating-review.xlsx`);
const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
await fs.writeFile(`${output}/executive-report.html`, `<!doctype html><html lang="en"><meta charset="utf-8"><title>Operating review</title><style>body{font:16px Arial;max-width:900px;margin:50px auto;color:#243342}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}</style><h1>Operating review</h1><p>${escape(model.case_id)} / ${escape(impact.period)}</p><h2>Reserve: USD ${escape(brief.reserve_amount.toFixed(2))}</h2><p>Requested: ${escape(brief.demand_quantity)}. Committed: ${escape(brief.committed_quantity)}. Shortfall: ${escape(brief.unfilled_quantity)}.</p><p>Decision: ${escape(brief.decision_status)}</p><h2>Customer commitments</h2><table><tr><th>Order</th><th>Committed</th><th>Shortfall</th><th>Status</th></tr>${schedule.orders.map(o=>`<tr><td>${escape(o.order_id)}</td><td>${escape(o.committed_quantity)}</td><td>${escape(o.shortfall_quantity)}</td><td>${escape(o.status)}</td></tr>`).join('')}</table></html>`);
