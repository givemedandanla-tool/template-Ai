// Synthetic Adobe object model: exercises our control flow, not Illustrator's implementation.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(path.join(__dirname, '../../../template_ai/review_tool/illustrator_export.jsx'), 'utf8');
function run(mode) {
  const request = {source:'C:/synthetic/input.ai', output:'C:/synthetic/copy.pdf', cancel:'C:/synthetic/cancel'};
  let closed = 0, saved = 0, opened = 0, cancelled = mode === 'cancel-before', options;
  function File(value) { this.fsName=value; this.name=value.split('/').pop(); Object.defineProperty(this, 'exists', {get:()=>value===request.source ? mode!=='missing' : value===request.cancel ? cancelled : mode==='exists'}); }
  const doc = {fullName:new File(request.source), artboards:{length:mode==='limit'?101:2},
    saveAs(output, opts) { saved++; options=opts; assert.equal(output.fsName, request.output); if(mode==='save-fails') throw Error('private text'); if(mode==='cancel-save') cancelled=true; },
    close(value) { assert.equal(value, 9); closed++; if(mode==='close-fails') throw Error('private'); }};
  const existing = {fullName:new File('C:/synthetic/other.ai'), close(){throw Error('Must not close existing');}};
  const context = {File, PDFSaveOptions:function(){}, PDFCompatibility:{ACROBAT6:6}, SaveOptions:{DONOTSAVECHANGES:9}, UserInteractionLevel:{DISPLAYALERTS:1},
    app:{documents:mode==='open'?[doc]:[existing], userInteractionLevel:mode==='alerts-off'?0:1,
      open(file) { opened++; assert.equal(file.fsName,request.source); if(mode==='open-fails') throw Error('private'); if(mode==='alias')return existing; if(mode==='cancel-open')cancelled=true; return doc; }}};
  vm.createContext(context); vm.runInContext(source,context);
  const result=context.reviewExport(request);
  return {result, closed, saved, opened, options};
}
const cases = [
 ['success','OK|2',1,1],['missing','INVALID_SOURCE',0,0],['exists','OUTPUT_EXISTS',0,0],
 ['open','SOURCE_OPEN',0,0],['alias','SOURCE_OPEN',0,0],['alerts-off','ALERTS_DISABLED',0,0],
 ['cancel-before','CANCELLED',0,0],['cancel-open','CANCELLED',1,0],['cancel-save','CANCELLED',1,1],
 ['open-fails','EXPORT_FAILED',0,0],['save-fails','EXPORT_FAILED',1,1],['close-fails','CLOSE_FAILED',1,1],
 ['limit','PAGE_LIMIT',1,0],['other-document','OK|2',1,1]
];
for(const [mode, result, closed, saved] of cases) {
  const actual=run(mode); assert.equal(actual.result,result,mode); assert.equal(actual.closed,closed,mode); assert.equal(actual.saved,saved,mode);
  if(saved) { assert.equal(actual.options.artboardRange,''); assert.equal(actual.options.preserveEditability,false); assert.equal(actual.options.compatibility,6); }
}
process.stdout.write(JSON.stringify({passed:cases.length, failed:0, adobe_runtime:false}));
