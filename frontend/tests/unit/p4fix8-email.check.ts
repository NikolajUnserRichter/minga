import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import { getErrorMessage } from '../../src/services/errors.ts';
import { hatEineRolle, ROLLEN_OHNE_HALLE } from '../../src/services/rollen.ts';

function ausfuehren(datei: string, auswahl: (node: ts.Statement) => boolean, context: object) {
  const text = readFileSync(new URL(datei, import.meta.url), 'utf8');
  const quelle = ts.createSourceFile(datei, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const code = quelle.statements.filter(auswahl).map(node => node.getText(quelle)).join('\n');
  const js = ts.transpileModule(code, { compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React,
  }}).outputText;
  vm.runInNewContext(js, context);
}

const requests: Array<{ pfad: string; daten: any }> = [];
const senden = async (pfad: string, daten: unknown) => {
  requests.push({ pfad, daten: JSON.parse(JSON.stringify(daten)) });
  return { data: {} };
};
const apiContext = { exports: {} as any, api: { post: senden, patch: senden } };
ausfuehren('../../src/services/api.ts', node => ts.isFunctionDeclaration(node) || (
  ts.isVariableStatement(node) && node.declarationList.declarations.some(
    declaration => declaration.name.getText() === 'salesApi')), apiContext);
const salesApi = apiContext.exports.salesApi;
const fehler: string[] = [];
let pruefungen = 0;
function pruefen(name: string, check: () => void) {
  pruefungen++;
  try { check(); } catch (error) { fehler.push(`${name}: ${String(error)}`); }
}
for (const methode of ['createCustomer', 'updateCustomer', 'createContact', 'updateContact']) {
  for (const email of ['', '   ', null, undefined, 'kontakt@test.example']) {
    const daten = { name: 'Testkontakt', ...(email === undefined ? {} : { email }) };
    const args = methode === 'createCustomer' ? [daten]
      : methode === 'updateContact' ? ['kunde', 'kontakt', daten] : ['kunde', daten];
    await salesApi[methode](...args);
    pruefen(`${methode}: ${String(email)}`, () => {
      const gesendet = requests.at(-1)!.daten;
      if (email === undefined) assert.equal('email' in gesendet, false);
      else assert.equal(gesendet.email, email?.trim() || null);
      assert.equal(gesendet.name, 'Testkontakt');
      assert.equal(daten.email, email);
    });
  }
}

const mutations: any[] = [];
const toasts: string[] = [];
const context = {
  React: { createElement: () => ({}) }, Button: 'button', Input: 'input', Select: 'select',
  Plus: 'plus', Trash: 'trash', getErrorMessage, hatEineRolle, ROLLEN_OHNE_HALLE, salesApi,
  useQueryClient: () => ({ invalidateQueries: () => {} }), useQuery: () => ({ data: [] }),
  useMutation: (config: any) => { mutations.push(config); return { mutate: () => {} }; },
  useState: (initial: unknown) => [initial, () => {}],
  useToast: () => ({ error: (text: string) => toasts.push(text) }),
  useAuth: () => ({ user: { roles: ['admin'] } }),
};
ausfuehren('../../src/pages/Customers.tsx', node => ts.isFunctionDeclaration(node) &&
  node.name?.text === 'ContactList', context);
vm.runInNewContext('ContactList({ customerId: "kunde" })', context);
mutations[0].onError({ response: { data: { detail: [
  { loc: ['body', 'email'], msg: 'E-Mail ist ungültig' },
] } } });
pruefen('Kontakt-Fehlertoast', () => assert.equal(toasts[0], 'email: E-Mail ist ungültig'));
assert.deepEqual(fehler, [], `${fehler.length} von ${pruefungen} Prüfungen fehlgeschlagen`);
console.log(`p4fix8-email.check: ${pruefungen} Fälle ok`);
