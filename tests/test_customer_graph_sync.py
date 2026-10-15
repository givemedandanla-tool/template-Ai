"""UI045：真實 SQLite、穩定身分、失敗注入及實際 Qt 工作台。"""
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from template_ai import customer_sync
from template_ai.customer_sync_dialog import CustomerSyncDialog
from template_ai.customers import CustomerStore
from template_ai.demo import demo_template
from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])


class CustomerGraphSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.library = Library(self.temp.name)
        self.store = CustomerStore(self.library)
        self.template = demo_template()
        self.library.save_template(self.template)
        graph = InputGraph.from_legacy([{'name': ['Alex Example'], 'phone': ['0100'],
            'email': ['alex@example.test'], 'company': 'c1'}], [{'name': 'Example Company'}])
        self.customer = self.store.create_graph('00001', 'Synthetic customer', graph.data,
                                                self.template.id, approved=True)

    def tearDown(self):
        self.library.close()
        self.temp.cleanup()

    def field(self, graph, kind):
        return next(f for f in graph.data['fields'] if f['kind'] == kind)

    def test_selective_values_use_stable_ids_and_never_change_work_or_templates(self):
        graph = InputGraph(self.customer['graph'])
        phone = self.field(graph, 'phone')['id']
        email = self.field(graph, 'email')['id']
        graph.command('edit_field', field_id=phone, value='0200')
        graph.command('edit_field', field_id=email, value='work-only@example.test')
        original = deepcopy(graph.data)
        before = deepcopy(self.template.to_dict())
        plan = customer_sync.differences(self.store, self.customer, graph.data)
        self.assertEqual(len(plan['rows']), 2)
        with self.assertRaises(ValueError):
            customer_sync.writeback(self.store, self.customer, graph.data, [], True)
        updated = customer_sync.writeback(self.store, self.customer, graph.data,
                                          ['fields:' + phone], True)
        self.assertEqual(InputGraph(updated['graph']).field(phone)['value'], '0200')
        self.assertEqual(InputGraph(updated['graph']).field(email)['value'], 'alex@example.test')
        self.assertEqual(original, graph.data)
        self.assertEqual(before, self.library.templates()[0].to_dict())
        self.assertEqual(updated['code'], '00001')

    def test_add_delete_clear_and_absent_are_distinct_and_names_protected(self):
        graph = InputGraph(self.customer['graph'])
        phone = self.field(graph, 'phone')['id']
        email = self.field(graph, 'email')['id']
        graph.command('edit_field', field_id=phone, value='')
        graph.command('delete_field', field_id=email, approved=True)
        graph.command('add_field', owner_id=graph.data['people'][0]['id'], kind='line', value='synthetic-line')
        rows = customer_sync.differences(self.store, self.customer, graph.data)['rows']
        self.assertEqual({r['operation'] for r in rows}, {'ADD', 'DELETE', 'EDIT'})
        updated = customer_sync.writeback(self.store, self.customer, graph.data,
                                          [r['id'] for r in rows], True)
        self.assertEqual(InputGraph(updated['graph']).field(phone)['value'], '')
        self.assertFalse(any(f['id'] == email for f in updated['fields']))
        self.assertEqual(self.field(InputGraph(updated['graph']), 'line')['value'], 'synthetic-line')
        bad = InputGraph(updated['graph'])
        name = next(f['id'] for f in bad.data['fields'] if f['kind'] == 'name' and
                    f['owner_id'] == bad.data['people'][0]['id'])
        bad.command('edit_field', field_id=name, value='')
        with self.assertRaisesRegex(ValueError, '名稱不可清空'):
            customer_sync.writeback(self.store, updated, bad.data, ['fields:' + name], True)
        self.assertEqual(self.store.get(updated['id']), updated)

    def test_shared_company_and_contacts_preview_all_actual_owners(self):
        graph = InputGraph(self.customer['graph'])
        first = graph.data['people'][0]['id']
        graph.command('add_person', name='Casey Example')
        other = graph.data['people'][-1]['id']
        company = graph.data['companies'][0]['id']
        graph.command('link_company', person_id=other, company_id=company, approved=True)
        phone = self.field(graph, 'phone')['id']
        graph.command('link_field', field_id=phone, entity_id=other, approved=True)
        rows = customer_sync.differences(self.store, self.customer, graph.data)['rows']
        shared = next(r for r in rows if r['id'] == 'fields:' + phone)
        self.assertEqual(set(shared['affected']), {first, other})
        updated = customer_sync.writeback(self.store, self.customer, graph.data,
                                          [r['id'] for r in rows], True)
        self.assertEqual(len(updated['graph']['people']), 2)
        self.assertEqual(set(InputGraph(updated['graph']).field(phone)['users']), {first, other})

    def test_partial_dependent_set_is_rejected_without_implicit_selection(self):
        graph = InputGraph(self.customer['graph'])
        graph.command('add_person', name='Casey Example')
        other = graph.data['people'][-1]['id']
        with self.assertRaisesRegex(ValueError, '名稱欄位'):
            customer_sync.writeback(self.store, self.customer, graph.data, ['people:' + other], True)
        self.assertEqual(self.store.get(self.customer['id']), self.customer)
        self.assertEqual(self.store.history(self.customer['id']), [])

    def test_stale_snapshot_has_three_values_and_never_overwrites_later_write(self):
        original = InputGraph(self.customer['graph'])
        phone = self.field(original, 'phone')['id']
        first = original.clone()
        first.command('edit_field', field_id=phone, value='first writer')
        updated = customer_sync.writeback(self.store, self.customer, first.data, ['fields:' + phone], True)
        original.command('edit_field', field_id=phone, value='stale writer')
        plan = customer_sync.differences(self.store, self.customer, original.data)
        self.assertTrue(plan['stale'])
        row = plan['rows'][0]
        self.assertEqual([row[k]['value'] for k in ('before', 'current', 'after')],
                         ['0100', 'first writer', 'stale writer'])
        with self.assertRaisesRegex(ValueError, '主檔已更新'):
            customer_sync.writeback(self.store, self.customer, original.data, ['fields:' + phone], True)
        self.assertEqual(self.store.get(updated['id']), updated)

    def test_late_event_failure_rolls_back_entities_contacts_links_history_and_revision(self):
        graph = InputGraph(self.customer['graph'])
        graph.command('add_person', name='Casey Example')
        phone = self.field(graph, 'phone')['id']
        graph.command('edit_field', field_id=phone, value='not committed')
        rows = customer_sync.differences(self.store, self.customer, graph.data)['rows']
        with patch.object(self.library, 'event', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                customer_sync.writeback(self.store, self.customer, graph.data, [r['id'] for r in rows], True)
        self.assertEqual(self.store.get(self.customer['id']), self.customer)
        self.assertEqual(self.store.history(self.customer['id']), [])
        self.assertEqual(self.library.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_logo_and_cross_customer_operations_cannot_use_generic_sync(self):
        graph = InputGraph(self.customer['graph'])
        graph.command('edit_logo', company_id=graph.data['companies'][0]['id'], logo_id='forged', approved=True)
        with self.assertRaisesRegex(ValueError, 'Logo'):
            customer_sync.differences(self.store, self.customer, graph.data)
        graph = InputGraph(self.customer['graph'])
        phone = self.field(graph, 'phone')['id']
        graph.command('edit_field', field_id=phone, value='not applied')
        with self.assertRaisesRegex(ValueError, '非本次差異'):
            customer_sync.writeback(self.store, self.customer, graph.data, ['fields:another-customer'], True)
        self.assertEqual(self.store.get(self.customer['id']), self.customer)

    def test_restore_is_new_revision_then_preserves_later_values_and_history_can_be_deleted(self):
        graph = InputGraph(self.customer['graph'])
        phone = self.field(graph, 'phone')['id']
        graph.command('edit_field', field_id=phone, value='0200')
        updated = customer_sync.writeback(self.store, self.customer, graph.data, ['fields:' + phone], True)
        record = self.store.history(updated['id'])[0]
        reverse, plan = customer_sync.restore_plan(self.store, updated, record['id'])
        restored = customer_sync.writeback(self.store, updated, reverse, [r['id'] for r in plan['rows']],
                                            True, restore_of=record['id'])
        self.assertEqual(restored['revision'], 3)
        self.assertEqual(InputGraph(restored['graph']).field(phone)['value'], '0100')
        with self.assertRaisesRegex(ValueError, '之後已有修改'):
            customer_sync.restore_plan(self.store, restored, record['id'])
        customer_sync.delete_history(self.store, restored, record['id'], True)
        self.assertNotIn(record['id'], [r['id'] for r in self.store.history(restored['id'])])

    def test_actual_dialog_default_work_only_cancel_confirmation_and_commit(self):
        window = MainWindow(self.temp.name + '-gui')
        try:
            window.reorder_customer_snapshot = self.customer
            graph = InputGraph(self.customer['graph'])
            phone = self.field(graph, 'phone')['id']
            graph.command('edit_field', field_id=phone, value='dialog new phone')
            window.active_input_graph = graph
            dialog = CustomerSyncDialog(window, self.store, self.customer)
            self.assertEqual(dialog.selected(), [])
            dialog.commit()
            self.assertEqual(self.store.get(self.customer['id']), self.customer)
            dialog.table.item(0, 0).setCheckState(Qt.Checked)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
                dialog.commit()
            self.assertEqual(self.store.get(self.customer['id']), self.customer)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                dialog.commit()
            updated = self.store.get(self.customer['id'])
            self.assertEqual(InputGraph(updated['graph']).field(phone)['value'], 'dialog new phone')
            self.assertEqual(window.active_input_graph.data, graph.data)
            dialog.close()
        finally:
            window.library.close()
            window.deleteLater()
