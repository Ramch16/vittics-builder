const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('vittics_builder/static/index.html', 'utf8');
const code = html.slice(html.indexOf('let refreshPromise = null;'), html.indexOf('let operationsLoading'));
function setup() {
  const pending = [], elements = {};
  let requests = 0, renders = 0;
  const context = vm.createContext({
    token: 'test', state: null, document: {hidden: false, activeElement: {}},
    openChatId: null, watching: null, reportFor: null, feedbackFor: null, openTicketId: null,
    $: id => elements[id] ||= {},
    api: () => {requests++; return new Promise(resolve => pending.push(resolve));},
    render: () => renders++, signOut: () => {},
  });
  vm.runInContext(code, context);
  return {context, pending, requests: () => requests, renders: () => renders};
}
test('slow polling coalesces while forced refresh gets a new snapshot', async () => {
  const s = setup();
  const first = s.context.refresh();
  const second = s.context.refresh();
  const forced = s.context.refresh(true);
  assert.equal(s.requests(), 1);
  s.pending.shift()({revision: 1});
  await first; await second;
  assert.equal(s.requests(), 2);
  s.pending.shift()({revision: 2});
  await forced;
  assert.equal(s.context.state.revision, 2);
});
test('hidden tabs pause polling and explicit actions still refresh', async () => {
  const s = setup(); s.context.document.hidden = true;
  await s.context.refresh(); assert.equal(s.requests(), 0);
  const forced = s.context.refresh(true);
  s.pending.shift()({revision: 1}); await forced;
  assert.equal(s.requests(), 1);
});
test('responses from a previous login cannot replace current state', async () => {
  const s = setup(); const refresh = s.context.refresh();
  s.context.token = 'different'; s.pending.shift()({revision: 1}); await refresh;
  assert.equal(s.context.state, null); assert.equal(s.renders(), 0);
});
test('editing pauses redraw while keeping state current', async () => {
  const s = setup(); s.context.document.activeElement = {tagName: 'INPUT'};
  const refresh = s.context.refresh(); s.pending.shift()({revision: 3}); await refresh;
  assert.equal(s.context.state.revision, 3); assert.equal(s.renders(), 0);
});
test('typing that begins during a slow request also prevents redraw', async () => {
  const s = setup(); const refresh = s.context.refresh();
  s.context.document.activeElement = {tagName: 'TEXTAREA'};
  s.pending.shift()({revision: 4}); await refresh;
  assert.equal(s.context.state.revision, 4); assert.equal(s.renders(), 0);
});
test('slow chat panels do not delay the main snapshot redraw', async () => {
  const s = setup(); let finishChat;
  s.context.openChatId = 1;
  s.context.loadChat = () => new Promise(resolve => {finishChat = resolve;});
  const refresh = s.context.refresh(); s.pending.shift()({revision: 5});
  await new Promise(setImmediate);
  assert.equal(s.renders(), 1);
  const duplicate = s.context.refresh(); assert.equal(s.requests(), 1);
  finishChat(); await refresh; await duplicate;
});
