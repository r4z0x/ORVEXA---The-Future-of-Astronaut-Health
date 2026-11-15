import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import time
import json
import csv
import sqlite3
import threading
from pathlib import Path
from datetime import datetime,timezone,timedelta
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QTableWidget,QTextBrowser
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from orvexa.ui import MainWindow
from orvexa.dialogs import MetricsDialog,WorkoutDialog
from orvexa.domain import Metrics,sample_plan,validate_ai_analysis
from orvexa.storage import Repository
from orvexa.ai import AIConfig
from orvexa.widgets import HealthChart

app=QApplication.instance() or QApplication([])

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.window=MainWindow(Repository(self.tmp.name))
        self.window.show()
        app.processEvents()

    def tearDown(self):
        self.window.close()
        app.processEvents()
        self.tmp.cleanup()

    def test_all_native_views_render(self):
        for view in ['overview','health','assistant','training','reports','settings']:
            with self.subTest(view=view):
                self.window.show_view(view)
                app.processEvents()
                self.assertFalse(self.window.grab().isNull())

    def test_manual_input_saves_and_invalidates_analysis(self):
        def fill_dialog(dialog):
            dialog.fields['heart'].setValue(77)
            dialog.sleep_hours.setValue(7)
            dialog.sleep_minutes.setValue(45)
            dialog.confirm()
            return QDialog.DialogCode.Accepted
        with patch.object(MetricsDialog,'exec',fill_dialog):
            self.window.edit_metrics()
        self.assertEqual(self.window.metrics.heart,77)
        self.assertEqual(self.window.metrics.sleep_hours,7.75)
        self.assertEqual(len(self.window.repo.measurements()),1)
        self.assertIsNone(self.window.analysis)

    def test_async_analysis_reaches_gui_and_database(self):
        from tests.test_core import PLAN
        self.window.config=AIConfig(api_key='test')
        result=validate_ai_analysis(PLAN,model='test-model')
        with patch('orvexa.ai.AIClient.analyze',return_value=result):
            self.window.analyze()
            for _ in range(100):
                QTest.qWait(10)
                if not self.window.busy:
                    break
        self.assertFalse(self.window.busy)
        self.assertEqual(self.window.analysis.model,'test-model')
        self.assertEqual(self.window.repo.latest_analysis(None).plan[0].minutes,10)

    def test_timer_counts_actual_elapsed_time_and_finishes(self):
        dialog=WorkoutDialog(sample_plan(Metrics()),'sample',self.window)
        dialog.toggle_timer()
        dialog.last_tick=time.monotonic()-2
        dialog.tick()
        dialog.pause()
        self.assertGreaterEqual(dialog.elapsed,2)
        self.assertLess(dialog.elapsed,3)
        dialog.next_step()
        dialog.next_step()
        dialog.next_step()
        self.assertTrue(dialog.finished_session)
        self.assertEqual(dialog.completed,3)

    def payload(self,kind='analysis',result=None,job_id=1):
        from tests.test_core import PLAN
        self.window.active_job=job_id
        self.window.busy=True
        return {'job_id':job_id,'kind':kind,'measurement_id':self.window.current_id,'metrics':self.window.metrics,
                'error':None,'result':result if result is not None else validate_ai_analysis(PLAN)}

    def test_settings_draft_survives_navigation_and_background_result(self):
        self.window.show_view('settings')
        self.window.name_input.setText('Profile draft')
        self.window.model_input.setText('my-local-model')
        self.window.key_input.setText('private-draft-key')
        self.window.show_view('overview')
        self.window.show_view('settings')
        name_field=self.window.name_input
        self.window.job_finished(self.payload())
        self.assertIs(self.window.name_input,name_field)
        self.assertEqual(self.window.name_input.text(),'Profile draft')
        self.assertEqual(self.window.model_input.text(),'my-local-model')
        self.assertEqual(self.window.key_input.text(),'private-draft-key')

    def test_baseline_update_does_not_fabricate_measurement(self):
        from tests.test_core import PLAN
        current=self.window.repo.add_measurement(Metrics())
        self.window.current_id=current
        self.window.measurements=self.window.repo.measurements()
        self.window.repo.save_analysis(current,validate_ai_analysis(PLAN),Metrics())
        self.window.show_view('settings')
        self.window.baseline_input.setValue(65)
        self.window.save_profile()
        self.assertEqual(self.window.repo.counts()[0],1)
        self.assertEqual(self.window.repo.measurements()[0]['metrics']['baseline_heart'],61)
        self.assertEqual(self.window.metrics.baseline_heart,65)
        self.window.close()
        self.window=MainWindow(Repository(self.tmp.name))
        self.assertEqual(self.window.metrics.baseline_heart,65)
        self.assertIsNone(self.window.analysis)

    def test_failed_measurement_save_keeps_previous_state(self):
        original=self.window.metrics
        def fill(dialog):
            dialog.fields['heart'].setValue(77)
            return QDialog.DialogCode.Accepted
        with patch.object(MetricsDialog,'exec',fill),patch.object(self.window.repo,'add_measurement',side_effect=sqlite3.OperationalError('disk full')),patch('orvexa.ui.QMessageBox.warning') as warning:
            self.window.edit_metrics()
        self.assertEqual(self.window.metrics,original)
        self.assertIsNone(self.window.current_id)
        warning.assert_called_once()

    def test_chat_draft_and_input_survive_answer(self):
        self.window.show_view('assistant')
        self.window.chat_input.setText('Next question')
        field=self.window.chat_input
        self.window.job_finished(self.payload(kind='chat',result='First reply'))
        self.assertIs(self.window.chat_input,field)
        self.assertEqual(field.text(),'Next question')
        self.window.show_view('overview');self.window.show_view('assistant')
        self.assertEqual(self.window.chat_input.text(),'Next question')

    def test_cancelled_job_cannot_overwrite_newer_result(self):
        from tests.test_core import PLAN
        first_started=threading.Event()
        release_first=threading.Event()
        calls=[]
        first=validate_ai_analysis(PLAN,model='first')
        second=validate_ai_analysis(PLAN,model='second')
        def compute(client,metrics):
            calls.append(1)
            if len(calls)==1:
                first_started.set();release_first.wait(2);return first
            return second
        self.window.config=AIConfig(api_key='test')
        try:
            with patch('orvexa.ai.AIClient.analyze',compute):
                self.window.analyze()
                self.assertTrue(first_started.wait(1))
                self.window.cancel_job()
                self.window.analyze()
                for _ in range(100):
                    QTest.qWait(10)
                    if not self.window.busy:
                        break
                self.assertEqual(self.window.analysis.model,'second')
                release_first.set();QTest.qWait(50)
                self.assertEqual(self.window.analysis.model,'second')
                self.assertEqual(len(self.window.repo.export()['analyses']),1)
        finally:
            release_first.set()

    def test_empty_period_has_no_fake_measurement(self):
        current=self.window.repo.add_measurement(Metrics())
        self.window.repo.db.execute('UPDATE measurements SET at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=3)).isoformat(),current))
        self.window.repo.db.commit()
        self.window.current_id=current
        self.window.measurements=self.window.repo.measurements()
        self.window.chart_cache.clear()
        self.window.show_view('health')
        chart=self.window.chart_widget.findChild(HealthChart)
        self.assertEqual(chart.samples,[])
        self.assertEqual(self.window.chart_data('heart',1)[0],[])

    def test_chart_switch_keeps_page_and_bounds_render_cost(self):
        now=datetime.now(timezone.utc)
        self.window.repo.db.executemany('INSERT INTO measurements(at,data) VALUES(?,?)',
            [((now-timedelta(seconds=1000-i)).isoformat(),json.dumps(Metrics().to_dict())) for i in range(1000)])
        self.window.repo.db.commit()
        self.window.measurements=self.window.repo.measurements(limit=200)
        self.window.current_id=self.window.measurements[-1]['id']
        self.window.show_view('overview')
        page=self.window.scroll.widget()
        self.window.change_chart('spo2')
        self.assertIs(self.window.scroll.widget(),page)
        self.assertLessEqual(len(self.window.chart_widget.findChild(HealthChart).samples),600)
        self.window.show_view('reports')
        table=self.window.scroll.widget().findChild(QTableWidget)
        self.assertEqual(table.rowCount(),200)
        self.window.report_page(1)
        self.assertEqual(self.window.report_offset,200)
        self.assertEqual(self.window.scroll.widget().findChild(QTableWidget).rowCount(),200)

    def test_csv_extension_selects_csv_even_when_json_filter_selected(self):
        self.window.repo.add_measurement(Metrics())
        path=Path(self.tmp.name)/'export.csv'
        with patch('orvexa.ui.QFileDialog.getSaveFileName',return_value=(str(path),'JSON (*.json)')):
            self.window.export_report()
        with path.open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.reader(stream,delimiter=';'))
        self.assertEqual(rows[0][0],'Date')
        self.assertEqual(len(rows),2)

    def test_sleep_limit_and_finished_timer_do_not_overrun(self):
        metrics=MetricsDialog(Metrics(),self.window)
        metrics.sleep_hours.setValue(16)
        self.assertEqual(metrics.sleep_minutes.maximum(),0)
        self.assertEqual(metrics.metrics().sleep_hours,16)
        metrics.deleteLater()
        exercise=sample_plan(Metrics())[0]
        dialog=WorkoutDialog((exercise,),'sample',self.window)
        dialog.toggle_timer()
        dialog.last_tick=time.monotonic()-10000
        dialog.tick()
        self.assertEqual(dialog.elapsed,exercise.minutes*60)
        self.assertFalse(dialog.running)
        dialog.next_step();dialog.next_step()
        self.assertEqual(dialog.completed,1)
        self.assertFalse(dialog.timer.isActive())
        dialog.deleteLater()

    def test_partial_workout_save_and_cancel(self):
        from PySide6.QtWidgets import QMessageBox
        dialog=WorkoutDialog(sample_plan(Metrics()),'sample',self.window)
        dialog.elapsed=10
        with patch('orvexa.dialogs.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):
            dialog.reject()
        self.assertFalse(dialog.finished_session)
        with patch('orvexa.dialogs.QMessageBox.question',return_value=QMessageBox.StandardButton.Save):
            dialog.reject()
        self.assertTrue(dialog.finished_session)
        self.assertEqual(dialog.completed,0)
        dialog.deleteLater()

    def test_long_exercise_instructions_are_scrollable(self):
        from dataclasses import replace
        exercise=replace(sample_plan(Metrics())[0],steps='Move smoothly and follow instructor guidance. '*30)
        dialog=WorkoutDialog((exercise,),'ai',self.window)
        dialog.show();app.processEvents()
        instructions=dialog.findChild(QTextBrowser)
        self.assertEqual(instructions.toPlainText(),exercise.steps)
        self.assertGreater(instructions.verticalScrollBar().maximum(),0)
        self.assertLessEqual(dialog.height(),app.primaryScreen().availableGeometry().height())
        dialog.accept();dialog.deleteLater()

    def test_full_flow_through_local_model_and_export(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from tests.test_core import PLAN
        requests=[]
        class LocalModel(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'done':True,'message':{'content':json.dumps(PLAN,ensure_ascii=False)}}).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),LocalModel)
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True)
        thread.start()
        try:
            def enter_metrics():
                dialog=app.activeModalWidget()
                self.assertIsInstance(dialog,MetricsDialog)
                dialog.fields['heart'].setValue(70)
                dialog.sleep_hours.setValue(7)
                dialog.sleep_minutes.setValue(30)
                dialog.confirm()
            QTimer.singleShot(0,enter_metrics)
            self.window.edit_metrics()
            self.assertEqual(self.window.metrics.heart,70)
            self.window.config=AIConfig('Ollama','test-model',ollama_url=f'http://127.0.0.1:{server.server_port}')
            with patch('orvexa.ui.QMessageBox.warning') as warning:
                self.window.analyze()
                for _ in range(200):
                    QTest.qWait(10)
                    if not self.window.busy:
                        break
                warning.assert_not_called()
            self.assertFalse(self.window.busy)
            self.assertEqual(self.window.analysis.plan[0].name,'Mobility & Stretching')
            submitted=json.loads(requests[0]['messages'][1]['content'])
            self.assertEqual(submitted['metrics']['heart'],70)
            def complete_session():
                dialog=app.activeModalWidget()
                self.assertIsInstance(dialog,WorkoutDialog)
                dialog.toggle_timer()
                dialog.last_tick=time.monotonic()-3
                dialog.tick()
                dialog.next_step()
            QTimer.singleShot(0,complete_session)
            self.window.start_workout()
            self.assertEqual(self.window.repo.sessions()[0]['completed'],1)
            self.assertEqual(self.window.repo.sessions()[0]['seconds'],3)
            report=Path(self.tmp.name)/'complete-report.json'
            with patch('orvexa.ui.QFileDialog.getSaveFileName',return_value=(str(report),'JSON (*.json)')):
                self.window.export_report()
            data=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['measurements'][0]['metrics']['heart'],70)
            self.assertEqual(data['analyses'][0]['analysis']['mode'],'ai')
            self.assertEqual(data['sessions'][0]['mode'],'ai')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_small_desktop_window_keeps_controls_accessible(self):
        self.window.resize(1060,730)
        app.processEvents()
        self.assertFalse(self.window.mission_card.isVisible())
        for view in ['overview','health','assistant','training','reports','settings']:
            with self.subTest(view=view):
                self.window.show_view(view);app.processEvents()
                self.assertLessEqual(self.window.scroll.widget().width(),self.window.scroll.viewport().width())
                self.assertTrue(all(nav.height()>=35 for nav in self.window.nav.values()))

if __name__=='__main__':
    unittest.main()
