"""Native desktop views. UI stays responsive while network inference runs."""
import html
import os
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QScrollArea, QButtonGroup, QDialog, QMessageBox, QLineEdit, QComboBox,
    QFileDialog, QTextBrowser, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDoubleSpinBox, QApplication, QPushButton)
from .ai import AIClient, AIConfig
from .domain import Metrics, sample_plan, safety_analysis, sleep_label
from .storage import Repository
from .widgets import ASSETS, Card, Hero, MetricCard, HealthChart, label, button, row, make_icon
from .theme import STYLE
from .dialogs import MetricsDialog, WorkoutDialog
from .reports import save_report

VIEWS={'overview':('Mission Overview','grid'),'health':('Health Metrics','pulse'),
       'assistant':('AI Assistant','spark'),'training':('Workouts','dumbbell'),
       'reports':('Reports','file'),'settings':('Settings','gear')}

class JobSignals(QObject):
    finished=Signal(object)

class MainWindow(QMainWindow):
    _font_ready=False
    PAGE_SIZE=200
    def __init__(self, repository=None):
        super().__init__()
        font_file=ASSETS/'GolosText.ttf'
        if not self._font_ready and font_file.exists():
            QFontDatabase.addApplicationFont(str(font_file))
            MainWindow._font_ready=True
        QApplication.instance().setFont(QFont('Golos Text',10))
        QApplication.instance().setStyleSheet(STYLE)
        self.setWindowTitle('ORVEXA — Crew Health System')
        self.setWindowIcon(make_icon('spark','#54d8f4',64))
        self.resize(1390,940)
        self.setMinimumSize(1060,730)
        self.repo=repository or Repository()
        self.measurements=self.repo.measurements(limit=self.PAGE_SIZE)
        self.current_id=self.measurements[-1]['id'] if self.measurements else None
        self.metrics=Metrics.from_dict(self.measurements[-1]['metrics']) if self.measurements else Metrics()
        try:
            self.metrics=replace(self.metrics,baseline_heart=self.repo.get_setting('baseline',self.metrics.baseline_heart)).validate()
        except ValueError:
            pass
        self.analysis=self.repo.latest_analysis(self.current_id,self.metrics) if self.current_id is not None else None
        self.name=str(self.repo.get_setting('name','Crew Member 04')).strip() or 'Crew Member 04'
        self.role=str(self.repo.get_setting('role','Mission Specialist')).strip() or 'Mission Specialist'
        self.config=AIConfig(provider=self.repo.get_setting('provider','OpenAI'),model=self.repo.get_setting('model','gpt-4.1-mini'),
                             api_key=os.getenv('OPENAI_API_KEY',''),ollama_url=self.repo.get_setting('ollama_url','http://127.0.0.1:11434'))
        self.view='overview'
        self.chart_key='heart'
        self.chart_period=1
        self.busy=False
        self.chat=[]
        self.chat_draft=''
        self.settings_draft=None
        self.chart_cache={}
        self.report_offset=0
        self.chart_widget=None
        self.ai_widget=None
        self._page_initialized=False
        self._closing=False
        self.job_counter=0
        self.active_job=None
        self.signals=JobSignals(self)
        self.signals.finished.connect(self.job_finished)
        self.build_shell()
        self.show_view('overview')

    def build_shell(self):
        root=QWidget()
        shell=QHBoxLayout(root)
        shell.setContentsMargins(0,0,0,0)
        shell.setSpacing(0)
        self.setCentralWidget(root)
        sidebar=QFrame()
        sidebar.setObjectName('Sidebar')
        sidebar.setFixedWidth(215)
        side=QVBoxLayout(sidebar)
        side.setContentsMargins(16,28,16,20)
        side.setSpacing(8)
        brand=label('ORVEXA',29,'#e9f6ff')
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(brand.styleSheet()+'letter-spacing:3px;')
        side.addWidget(brand)
        descriptor=label('CREW HEALTH SYSTEM',8,'#57778e')
        descriptor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(descriptor)
        side.addSpacing(31)
        side.addWidget(label('MISSION CONTROL',8,'#536f88'))
        side.addSpacing(8)
        self.nav={}
        group=QButtonGroup(self)
        group.setExclusive(True)
        for key,(title,icon) in VIEWS.items():
            if key=='settings':
                continue
            nav=button('  '+('Overview' if key=='overview' else title),lambda key=key:self.show_view(key),icon=icon)
            nav.setObjectName('Nav')
            nav.setCheckable(True)
            nav.setMinimumHeight(46)
            group.addButton(nav)
            self.nav[key]=nav
            side.addWidget(nav)
        side.addSpacing(25)
        mission=Card(padding=16)
        self.mission_card=mission
        mission.box.setSpacing(8)
        mission.box.addWidget(label('ORBITAL MISSION',8,'#65c9df'))
        mission.box.addWidget(label('Your home is orbit.',13,'#d8e9f7'))
        mission.box.addWidget(label('Your strength is your health.',10,'#829db7'))
        mission.box.addSpacing(7)
        mission.box.addWidget(label('━━━━━━━━━━━━━━',12,'#49cde9'))
        mission.box.addWidget(label('ISS-84 · Sample Expedition',8,'#637f99'))
        side.addWidget(mission)
        side.addStretch()
        settings=button('  Settings',lambda:self.show_view('settings'),icon='gear')
        settings.setObjectName('Nav')
        settings.setCheckable(True)
        group.addButton(settings)
        self.nav['settings']=settings
        side.addWidget(settings)
        help_button=button('  Help',self.show_help,icon='help',secondary=True)
        side.addWidget(help_button)
        side.addSpacing(14)
        self.profile_name=label(self.name,11,'#bfd5e7')
        self.profile_role=label(self.role+' · Crew 04',9,'#637f99')
        side.addWidget(self.profile_name)
        side.addWidget(self.profile_role)
        shell.addWidget(sidebar)
        right=QVBoxLayout()
        right.setSpacing(0)
        top=QFrame()
        top.setObjectName('Topbar')
        top.setFixedHeight(68)
        top_box=QHBoxLayout(top)
        top_box.setContentsMargins(29,0,29,0)
        self.breadcrumb=label('',10,'#89a4bb')
        top_box.addWidget(self.breadcrumb)
        top_box.addStretch()
        top_box.addWidget(label('●  DESKTOP APPLICATION',8,'#6cc5ad'))
        top_box.addSpacing(25)
        top_box.addWidget(label(datetime.now().strftime('%Y-%m-%d'),10,'#718aa2'))
        right.addWidget(top)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right.addWidget(self.scroll,1)
        shell.addLayout(right,1)
        self.statusBar().showMessage('ORVEXA · Data is stored on this computer')
        self.cancel_button=button('Cancel Request',self.cancel_job,secondary=True)
        self.cancel_button.hide()
        self.statusBar().addPermanentWidget(self.cancel_button)

    def resizeEvent(self,event):
        if hasattr(self,'mission_card'):
            self.mission_card.setVisible(self.height()>=860)
        super().resizeEvent(event)

    def capture_settings(self):
        if self._page_initialized and self.view=='settings':
            self.settings_draft={'name':self.name_input.text(),'role':self.role_input.text(),
                'baseline':self.baseline_input.value(),'provider':self.provider_input.currentText(),
                'model':self.model_input.text(),'api_key':self.key_input.text(),'url':self.url_input.text()}

    def show_view(self, key, preserve_scroll=False):
        old_scroll=self.scroll.verticalScrollBar().value() if preserve_scroll else 0
        self.capture_settings()
        self.view=key
        self.chart_widget=None
        self.ai_widget=None
        self.breadcrumb.setText('Crew  /  '+VIEWS[key][0])
        self.nav[key].setChecked(True)
        content=QWidget()
        content.setObjectName('Content')
        self.box=QVBoxLayout(content)
        self.box.setContentsMargins(28,24,28,24)
        self.box.setSpacing(19)
        getattr(self,'build_'+key)()
        self.box.addStretch()
        self.box.addWidget(label('●  ORVEXA  /  CREW HEALTH INTELLIGENCE                                        PYTHON DESKTOP',8,'#3f627b'))
        old=self.scroll.takeWidget()
        self.scroll.setWidget(content)
        if old:
            old.deleteLater()
        self._page_initialized=True
        self.cancel_button.setVisible(self.busy)
        if preserve_scroll:
            QTimer.singleShot(0,lambda:self.scroll.verticalScrollBar().setValue(old_scroll) if not self._closing else None)

    def heading(self,title,subtitle,export=False):
        text=QVBoxLayout()
        text.setSpacing(7)
        text.addWidget(label(title,25,'#eef7ff'))
        text.addWidget(label(subtitle,10,'#829bb4',wrap=True))
        action=button('Export Report' if export else 'Enter Data',self.export_report if export else self.edit_metrics,
                      icon='download' if export else 'plus')
        action.setObjectName('ExportButton' if export else 'MetricsButton')
        self.box.addLayout(row(text,None,action))

    def metric_cards(self):
        m=self.metrics
        defs=[('heart','Heart Rate',f'{m.heart:g}','bpm',f'Baseline: {m.baseline_heart:g} bpm','heart','#ed8eab',m.heart<45 or m.heart>110),
              ('spo2','SpO₂',f'{m.spo2:g}','%', 'Reference: 95–100%','drop','#5bcde9',m.spo2<95),
              ('temperature','Temperature',f'{m.temperature:.1f}','°C','Reference: 36.2–37.2 °C','temp','#e3b77f',not 36.2<=m.temperature<=37.2),
              ('sleep_hours','Sleep & Recovery',str(round(m.sleep_hours*60)//60),f'h {round(m.sleep_hours*60)%60:02d} min','Target: 7–9 hours','moon','#a99bec',not 7<=m.sleep_hours<=9)]
        layout=QHBoxLayout()
        layout.setSpacing(13)
        for key,title,value,unit,baseline,ic,color,warn in defs:
            values=self.chart_data(key,1)[0]
            note=('Below target' if m.sleep_hours<7 else 'Above target') if key=='sleep_hours' and warn else 'Attention' if warn else 'Within range'
            card=MetricCard(title,value,unit,baseline,ic,color,values,note,warn)
            card.clicked.connect(lambda key=key:self.select_metric(key))
            layout.addWidget(card,1)
        return layout

    def chart_data(self,key,period):
        now=datetime.now(timezone.utc)
        cache_key=(self.current_id,period,int(now.timestamp()//60))
        if self.current_id is not None:
            if cache_key not in self.chart_cache:
                records=self.repo.measurement_range(now-timedelta(days=period),now)
                stamps=[datetime.fromisoformat(r['at']).timestamp() for r in records]
                self.chart_cache={k:v for k,v in self.chart_cache.items() if k[2]==cache_key[2]}
                self.chart_cache[cache_key]=(records,stamps)
            records,stamps=self.chart_cache[cache_key]
            return [r['metrics'][key] for r in records],stamps
        base={'heart':[66,65,66,68,67,66,65,67,69,68,67,66,68,67,68,69,68,68],
              'spo2':[98,98,97,98,99,98,98,99,98,97,98,98,99,98,98,98,98,98],
              'temperature':[36.5,36.6,36.5,36.6,36.7,36.6,36.5,36.6,36.6,36.5,36.6,36.7,36.6,36.6,36.5,36.6,36.6,36.6],
              'sleep_hours':[7.3,7.1,6.9,7.4,6.8,7.0,6.7]}
        values=base[key]
        return values,[now.timestamp()-period*86400*(len(values)-1-i)/max(1,len(values)-1) for i in range(len(values))]

    def chart_card(self,wide=False):
        card=Card(padding=20)
        text=QVBoxLayout()
        text.setSpacing(5)
        text.addWidget(label('Metric Trends',14,'#dbeaf6'))
        text.addWidget(label('Saved Measurements' if self.measurements else 'DEMO · SAMPLE CHART',9,'#6f8da5'))
        periods=QHBoxLayout()
        periods.setSpacing(4)
        for days,title in [(1,'24 h'),(7,'7 days'),(30,'30 days')]:
            tab=button(title,lambda days=days:self.change_period(days))
            tab.setObjectName('Tab')
            tab.setCheckable(True)
            tab.setChecked(self.chart_period==days)
            tab.setMinimumHeight(27)
            periods.addWidget(tab)
        card.box.addLayout(row(text,None,periods))
        tabs=QHBoxLayout()
        tabs.setSpacing(6)
        for key,title in [('heart','Heart Rate'),('spo2','SpO₂'),('temperature','Temperature'),('sleep_hours','Sleep')]:
            tab=button(title,lambda key=key:self.change_chart(key))
            tab.setObjectName('Tab')
            tab.setCheckable(True)
            tab.setChecked(self.chart_key==key)
            tab.setMinimumHeight(26)
            tabs.addWidget(tab)
        tabs.addStretch()
        card.box.addLayout(tabs)
        values,stamps=self.chart_data(self.chart_key,self.chart_period)
        ticks=[]
        if stamps:
            span=stamps[-1]-stamps[0]
            for i in range(5 if span>0 else 1):
                position=i/4 if span>0 else .5
                stamp=stamps[0]+position*span
                ticks.append((position,datetime.fromtimestamp(stamp).strftime('%H:%M' if self.chart_period==1 else '%m-%d')))
        baseline={'heart':self.metrics.baseline_heart,'spo2':98,'temperature':36.6,'sleep_hours':8}[self.chart_key]
        unit={'heart':'bpm','spo2':'%','temperature':'°C','sleep_hours':'h'}[self.chart_key]
        chart=HealthChart(values,ticks,baseline,unit,self.current_id is None,timestamps=stamps)
        chart.setMinimumHeight(245 if wide else 166)
        card.box.addWidget(chart,1)
        if values:
            summary=f'Average  {sum(values)/len(values):.1f} {unit}        Minimum  {min(values):g}        Maximum  {max(values):g}'
            card.box.addWidget(label(summary,9,'#8ca7be'))
        if len(values)==1:
            card.box.addWidget(label('Add another measurement to view trends.',9,'#6f8da5'))
        self.chart_widget=card
        return card

    def current_analysis(self):
        return safety_analysis(self.metrics) if self.metrics.concerns() else self.analysis

    def ai_card(self):
        card=Card(padding=21)
        card.setObjectName('AI')
        card.setMinimumWidth(285)
        title=QVBoxLayout()
        title.setSpacing(4)
        title.addWidget(label('✦  ORVEXA Intelligence',14,'#dff7ff'))
        title.addWidget(label('INTELLIGENCE FOR EVERY ORBIT',8,'#66a5b4'))
        card.box.addLayout(row(title,None,label('AI' if self.analysis and self.analysis.mode=='ai' else 'SETUP',8,'#79b2c3')))
        analysis=self.current_analysis()
        card.box.addSpacing(3)
        card.box.addWidget(label(analysis.title if analysis else 'Every metric\nhas a story.',19,'#e4f5ff',wrap=True))
        summary=analysis.summary if analysis else 'Connect a model to get an explanation of current health status and a workout plan based on your measurements.'
        card.box.addWidget(label(summary,11,'#8fadc2',wrap=True))
        if analysis:
            card.box.addWidget(label('  ·  '.join(analysis.reasons[:2]),9,'#68bac8',wrap=True))
        else:
            card.box.addWidget(label('OpenAI API  ·  Local Ollama',9,'#68bac8'))
        card.box.addStretch()
        analyze=button('Analyzing…' if self.busy else 'Run AI Analysis',self.analyze,icon='spark',primary=True)
        analyze.setObjectName('AnalyzeButton')
        analyze.setEnabled(not self.busy)
        card.box.addWidget(analyze)
        card.box.addWidget(label('Draft recommendations for review by the mission medical officer',8,'#598393',wrap=True))
        self.ai_widget=card
        return card

    def training_section(self):
        plan=self.get_plan()
        start=button('Start Workout',self.start_workout,icon='play',primary=True)
        start.setEnabled(bool(plan))
        self.box.addLayout(row(label('Your Workout Today',15,'#dbeaf6'),None,start))
        if not plan:
            self.box.addWidget(self.notice('Workout Plan Paused' if self.metrics.concerns() else 'No Exercises Suggested',
                'Contact the mission medical officer to review the current readings.' if self.metrics.concerns() else
                'The model returned an analysis without exercises. Review its explanation or request a new analysis.'))
            return
        self.box.addWidget(label(f'{sum(e.minutes for e in plan)} min  ·  '+('AI-GENERATED PLAN' if self.analysis and self.analysis.mode=='ai' else 'SAMPLE PLAN · NO AI PLAN GENERATED YET'),9,'#6e91aa'))
        cards=QHBoxLayout()
        cards.setSpacing(13)
        icons=['dumbbell','cycle','move']
        colors=['#69cde6','#a59be9','#6bc7a8']
        for i,exercise in enumerate(plan):
            card=Card(padding=17)
            head=label(exercise.category,8,colors[i%3])
            symbol=label('',10)
            symbol.setPixmap(make_icon(icons[i%3],colors[i%3],26).pixmap(26,26))
            card.box.addLayout(row(symbol,None,head))
            card.box.addWidget(label(exercise.name,12,'#d9ebf8',wrap=True))
            card.box.addWidget(label(exercise.description,9,'#7897b0',wrap=True))
            card.box.addStretch()
            details=button('→',lambda exercise=exercise:self.exercise_details(exercise),secondary=True)
            details.setFixedWidth(30)
            details.setToolTip('Exercise Details')
            card.box.addLayout(row(label(f'{exercise.minutes} min  ·  {exercise.equipment}',9,'#8eabc1',wrap=True),None,details))
            cards.addWidget(card,1)
        self.box.addLayout(cards)

    def notice(self,title,text):
        card=Card(padding=15)
        card.setObjectName('Notice')
        card.box.setSpacing(5)
        card.box.addWidget(label(title,11,'#dfc28e'))
        card.box.addWidget(label(text,10,'#9f957f',wrap=True))
        return card

    def build_overview(self):
        self.heading('Mission Overview','Your health, monitored on every orbit.')
        self.box.addWidget(Hero(self.name,bool(self.metrics.concerns())))
        self.box.addLayout(row(label('Vital Signs',15,'#dbeaf6'),None,
            label('MANUAL ENTRY' if self.current_id else 'DEMO DATA',8,'#8a9dad')))
        self.box.addLayout(self.metric_cards())
        middle=QHBoxLayout()
        middle.setSpacing(18)
        middle.addWidget(self.chart_card(),5)
        middle.addWidget(self.ai_card(),3)
        self.box.addLayout(middle)
        self.training_section()
        self.box.addWidget(self.notice('Recovery Is Part of the Mission',
            f'Sleep duration: {sleep_label(self.metrics.sleep_hours)}. Consider your well-being and the crew schedule agreed with the mission team.'))

    def build_health(self):
        self.heading('Health Metrics','Turn individual readings into a clear picture of crew health.')
        self.box.addLayout(self.metric_cards())
        self.box.addWidget(self.chart_card(wide=True))
        details=Card()
        details.box.addWidget(label('Personal Profile',15,'#dfecf7'))
        for name,value in [('Resting Heart Rate Baseline',f'{self.metrics.baseline_heart:g} bpm'),
                           ('Change from Baseline',f'{self.metrics.heart-self.metrics.baseline_heart:+g} bpm'),
                           ('Self-Reported Fatigue',f'{self.metrics.fatigue:g} of 10'),
                           ('Pain or Discomfort','Reported' if self.metrics.symptoms else 'Not Reported')]:
            details.box.addLayout(row(label(name,11,'#819fb8'),None,label(value,11,'#c5dcec')))
        details.box.addWidget(label('Reference ranges are illustrative. Individual limits must be set by the mission medical officer.',10,'#687f95',wrap=True))
        self.box.addWidget(details)

    def build_training(self):
        self.heading('Movement. Even in Microgravity.','A plan informed by current readings and reported well-being.')
        self.box.addWidget(self.notice('Exercise Parameters Require Specialist Review',
            'The mission instructor and medical officer determine resistance, technique, intensity, and individual limitations.'))
        self.training_section()
        journal=Card()
        journal.box.addWidget(label('Workout Log',16,'#dcebf8'))
        sessions=self.repo.sessions(limit=8)
        if not sessions:
            journal.box.addWidget(label('Completed and saved workouts will appear here.',11,'#7e9bb3'))
        for session in sessions[:8]:
            at=datetime.fromisoformat(session['at']).astimezone().strftime('%Y-%m-%d  %H:%M')
            journal.box.addLayout(row(label(at,11,'#97b1c6'),None,
                label(f'{session["seconds"]/60:.1f} min  ·  {session["completed"]} exercises  ·  {"AI" if session["mode"]=="ai" else "Sample"}',10,'#71b9b5')))
        self.box.addWidget(journal)

    def build_assistant(self):
        self.heading('Your Orbital Assistant','Explanations of health metrics and guidance from the connected model.')
        card=Card()
        card.box.addLayout(row(label('ORVEXA Intelligence',17,'#dcf6ff'),None,
            label(self.config.provider+' / '+self.config.model,9,'#6daebf')))
        self.chat_browser=QTextBrowser()
        self.chat_browser.setMinimumHeight(330)
        self.chat_browser.setOpenExternalLinks(False)
        card.box.addWidget(self.chat_browser)
        self.update_chat()
        self.chat_input=QLineEdit()
        self.chat_input.setPlaceholderText('Ask about current health metrics or a workout…')
        self.chat_input.setMaxLength(2000)
        self.chat_input.setText(self.chat_draft)
        self.chat_input.textChanged.connect(self.set_chat_draft)
        self.chat_input.returnPressed.connect(self.send_chat)
        self.send_button=button('Send',self.send_chat,icon='arrow',primary=True)
        self.send_button.setEnabled(not self.busy)
        card.box.addLayout(row(self.chat_input,self.send_button))
        suggestions=QHBoxLayout()
        for question in ['How can I recover?','What is ARED used for?','How should short sleep be considered?']:
            suggestions.addWidget(button(question,lambda question=question:self.send_chat(question),secondary=True))
        suggestions.addStretch()
        card.box.addLayout(suggestions)
        card.box.addWidget(label('The model receives current metrics, your question, and chat context. The API key is not stored in the database.\nThis chat does not replace consultation with the mission medical officer.',9,'#66889f',wrap=True))
        self.box.addWidget(card)
        self.box.addWidget(self.ai_card())

    def set_chat_draft(self,text):
        self.chat_draft=text

    def update_chat(self):
        if not self.chat:
            text='<p style="color:#a8c2d9;line-height:1.8">Welcome! Connect OpenAI or a local Ollama model in Settings. I can help explain your readings and draft a workout plan.</p>'
        else:
            text=''.join(f'<p style="color:{"#7edcf5" if role=="You" else "#abc5da"};line-height:1.8"><b>{html.escape(role)}</b><br>{html.escape(message).replace(chr(10),"<br>")}</p>' for role,message in self.chat)
        self.chat_browser.setHtml(text)
        self.chat_browser.verticalScrollBar().setValue(self.chat_browser.verticalScrollBar().maximum())

    def build_reports(self):
        self.heading('Mission History','All measurements and workouts stored on this computer.',export=True)
        total,session_count,session_seconds=self.repo.counts()
        stats=QHBoxLayout()
        for title,value in [('Measurements Saved',str(total)),('Workouts Logged',str(session_count)),('Workout Time',f'{session_seconds/60:.1f} min')]:
            card=Card()
            card.box.addWidget(label(title,10,'#809eb6'))
            card.box.addWidget(label(value,29,'#dceefa'))
            stats.addWidget(card,1)
        self.box.addLayout(stats)
        if not total:
            self.box.addWidget(self.notice('No measurements have been logged yet','Add your first measurement. Demo values are not included in the history.'))
        else:
            records=self.repo.measurements(limit=self.PAGE_SIZE,offset=self.report_offset)
            table=QTableWidget(len(records),7)
            table.setHorizontalHeaderLabels(['Date','Heart Rate','SpO₂','Temp.','Sleep','Fatigue','Well-being'])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setAlternatingRowColors(True)
            table.setMinimumHeight(300)
            for i,entry in enumerate(reversed(records)):
                m=entry['metrics']
                fields=[datetime.fromisoformat(entry['at']).astimezone().strftime('%Y-%m-%d %H:%M'),f'{m["heart"]:g}',f'{m["spo2"]:g} %',f'{m["temperature"]:.1f} °C',sleep_label(m['sleep_hours']),str(m['fatigue']),'Discomfort' if m['symptoms'] else 'No Symptoms']
                for j,value in enumerate(fields):
                    table.setItem(i,j,QTableWidgetItem(value))
            self.box.addWidget(table)
            previous=button('← Newer',lambda:self.report_page(-1))
            previous.setEnabled(self.report_offset>0)
            following=button('Older →',lambda:self.report_page(1))
            following.setEnabled(self.report_offset+self.PAGE_SIZE<total)
            self.box.addLayout(row(previous,None,
                label(f'{self.report_offset+1}–{self.report_offset+len(records)} of {total}',10,'#88a4bc'),None,following))
        self.box.addWidget(label('JSON exports all data. CSV contains measurement history for spreadsheets.\nThese files contain health information. Store them securely.',10,'#68859d',wrap=True))

    def build_settings(self):
        self.heading('Application Settings','Crew profile and AI connection.')
        two=QHBoxLayout()
        two.setSpacing(20)
        profile=Card()
        profile.box.addWidget(label('Crew Profile',17,'#deedf8'))
        profile.box.addWidget(label('Name',10,'#88a4bc'))
        draft=self.settings_draft or {}
        self.name_input=QLineEdit(draft.get('name',self.name))
        self.name_input.setMaxLength(60)
        profile.box.addWidget(self.name_input)
        profile.box.addWidget(label('Crew Role',10,'#88a4bc'))
        self.role_input=QLineEdit(draft.get('role',self.role))
        self.role_input.setMaxLength(60)
        profile.box.addWidget(self.role_input)
        profile.box.addWidget(label('Resting Heart Rate Baseline (bpm)',10,'#88a4bc'))
        self.baseline_input=QDoubleSpinBox()
        self.baseline_input.setDecimals(0)
        self.baseline_input.setRange(35,110)
        self.baseline_input.setValue(draft.get('baseline',self.metrics.baseline_heart))
        profile.box.addWidget(self.baseline_input)
        profile.box.addWidget(label('Value set in consultation with the mission medical officer.',9,'#618198',wrap=True))
        profile.box.addStretch()
        profile.box.addWidget(button('Save Profile',self.save_profile,primary=True))
        ai=Card()
        ai.box.addWidget(label('AI Connection',17,'#deedf8'))
        ai.box.addWidget(label('Provider',10,'#88a4bc'))
        self.provider_input=QComboBox()
        self.provider_input.addItems(['OpenAI','Ollama'])
        self.provider_input.setCurrentText(draft.get('provider',self.config.provider))
        ai.box.addWidget(self.provider_input)
        ai.box.addWidget(label('Model',10,'#88a4bc'))
        self.model_input=QLineEdit(draft.get('model',self.config.model))
        ai.box.addWidget(self.model_input)
        self.key_label=label('OpenAI API Key · Memory Only',10,'#88a4bc')
        ai.box.addWidget(self.key_label)
        self.key_input=QLineEdit(draft.get('api_key',self.config.api_key))
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText('sk-… or OPENAI_API_KEY environment variable')
        ai.box.addWidget(self.key_input)
        self.url_label=label('Local Ollama URL',10,'#88a4bc')
        ai.box.addWidget(self.url_label)
        self.url_input=QLineEdit(draft.get('url',self.config.ollama_url))
        ai.box.addWidget(self.url_input)
        self.provider_note=label('',10,'#6d91a8',wrap=True)
        ai.box.addWidget(self.provider_note)
        ai.box.addWidget(button('Save Connection',self.save_ai_config,icon='spark',primary=True))
        self.provider_input.currentTextChanged.connect(self.provider_changed)
        self.provider_changed(self.provider_input.currentText(),initial=True)
        two.addWidget(profile,1)
        two.addWidget(ai,1)
        self.box.addLayout(two)
        self.box.addWidget(self.notice('Local Storage',str(self.repo.path)))
        self.box.addWidget(label('OpenAI sends metrics to an external service when you request an analysis or ask a question.\nOllama runs locally; download and start the model before use.',10,'#738fa6',wrap=True))

    def provider_changed(self,provider,initial=False):
        is_openai=provider=='OpenAI'
        self.key_input.setVisible(is_openai)
        self.key_label.setVisible(is_openai)
        self.url_input.setVisible(not is_openai)
        self.url_label.setVisible(not is_openai)
        self.provider_note.setText('An internet connection and an API key with available credits are required. The key is not saved to disk.' if is_openai else 'Start Ollama and run: ollama pull qwen2.5:7b. Data stays on this computer.')
        if not initial:
            self.model_input.setText('gpt-4.1-mini' if is_openai else 'qwen2.5:7b')

    def save_profile(self):
        name=self.name_input.text().strip()
        role=self.role_input.text().strip()
        if not name or not role:
            QMessageBox.warning(self,'Profile','Enter a crew member name and role.')
            return
        baseline=self.baseline_input.value()
        try:
            self.repo.set_settings({'name':name,'role':role,'baseline':baseline})
        except (sqlite3.Error,OSError) as exc:
            self.storage_error(exc)
            return
        self.name,self.role=name,role
        if baseline!=self.metrics.baseline_heart:
            self.metrics=replace(self.metrics,baseline_heart=baseline)
            self.analysis=None
            self.cancel_job(notify=False)
            self.chat=[]
        self.profile_name.setText(name)
        self.profile_role.setText(role+' · Crew 04')
        self.notify('Profile saved')

    def save_ai_config(self):
        try:
            config=AIConfig(self.provider_input.currentText(),self.model_input.text().strip(),
                            self.key_input.text().strip(),self.url_input.text().strip()).validate()
        except ValueError as exc:
            QMessageBox.warning(self,'Check Connection',str(exc))
            return
        try:
            self.repo.set_settings({'provider':config.provider,'model':config.model,'ollama_url':config.ollama_url})
        except (sqlite3.Error,OSError) as exc:
            self.storage_error(exc)
            return
        if config!=self.config:
            self.cancel_job(notify=False)
        self.config=config
        self.notify('Connection saved. The API key remains available until the app is closed.' if config.provider=='OpenAI' else 'Ollama connection saved.')

    def storage_error(self,exc):
        QMessageBox.warning(self,'Unable to Save Data','Check access to the data folder and available disk space.\n\n'+str(exc))

    def notify(self,message):
        self.statusBar().showMessage(message,10000)

    def change_period(self,days):
        self.chart_period=days
        self.refresh_chart()

    def change_chart(self,key):
        self.chart_key=key
        self.refresh_chart()

    def refresh_chart(self):
        old=self.chart_widget
        if old is None:
            return
        parent=old.parentWidget()
        replacement=self.chart_card(wide=self.view=='health')
        parent.layout().replaceWidget(old,replacement)
        old.hide()
        old.deleteLater()

    def report_page(self,direction):
        self.report_offset=max(0,self.report_offset+direction*self.PAGE_SIZE)
        self.show_view('reports',preserve_scroll=True)

    def select_metric(self,key):
        self.chart_key=key
        self.show_view('health')

    def edit_metrics(self):
        dialog=MetricsDialog(self.metrics,self)
        try:
            if dialog.exec()!=QDialog.DialogCode.Accepted:
                return
            metrics=dialog.metrics()
            try:
                new_id=self.repo.add_measurement(metrics)
            except (sqlite3.Error,OSError) as exc:
                self.storage_error(exc)
                return
            self.capture_settings()
            if self.settings_draft is not None:
                self.settings_draft['baseline']=metrics.baseline_heart
            self.metrics=metrics
            self.current_id=new_id
            self.measurements=self.repo.measurements(limit=self.PAGE_SIZE)
            self.chart_cache.clear()
            self.report_offset=0
            self.analysis=None
            self.chat=[]
            self.chat_draft=''
            self.cancel_job(notify=False)
            if self.view=='settings':
                self.baseline_input.setValue(metrics.baseline_heart)
            self.show_view(self.view,preserve_scroll=True)
            self.notify('Metrics saved. Request a new AI analysis.' if not self.metrics.concerns() else 'Metrics saved. The plan is paused pending medical review.')
        finally:
            dialog.deleteLater()

    def get_plan(self):
        if self.metrics.concerns():
            return ()
        return self.analysis.plan if self.analysis else sample_plan(self.metrics)

    def ready_for_ai(self):
        if self.metrics.concerns():
            return True
        if self.config.provider=='OpenAI' and not self.config.api_key.strip():
            self.show_view('settings')
            self.notify('Add an OpenAI API key or select local Ollama.')
            return False
        return True

    def run_job(self,kind,question=None):
        if self.busy or not self.ready_for_ai():
            return
        self.busy=True
        snapshot=self.metrics
        measurement_id=self.current_id
        config=self.config
        self.job_counter+=1
        job_id=self.job_counter
        self.active_job=job_id
        history=[{'role':'user' if role=='You' else 'assistant','content':text} for role,text in self.chat[:-1]] if kind=='chat' else []
        signal=self.signals.finished
        def task():
            try:
                client=AIClient(config)
                result=client.analyze(snapshot) if kind=='analysis' else client.chat(snapshot,question,history=history)
                payload={'job_id':job_id,'kind':kind,'result':result,'measurement_id':measurement_id,'metrics':snapshot,'error':None}
            except Exception as exc:
                payload={'job_id':job_id,'kind':kind,'result':None,'measurement_id':measurement_id,'metrics':snapshot,'error':str(exc)}
            try:
                signal.emit(payload)
            except RuntimeError:
                pass
        threading.Thread(target=task,daemon=True,name='orvexa-ai').start()
        self.refresh_job_ui()
        self.notify('The model is processing your request… The interface remains available.')

    def refresh_job_ui(self):
        if self.view=='assistant':
            self.update_chat()
            self.send_button.setEnabled(not self.busy)
        self.cancel_button.setVisible(self.busy)
        for control in self.scroll.widget().findChildren(QPushButton):
            if control.objectName()=='AnalyzeButton':
                control.setText('Analyzing…' if self.busy else 'Run AI Analysis')
                control.setEnabled(not self.busy)

    def cancel_job(self,notify=True):
        self.active_job=None
        self.busy=False
        if notify:
            self.refresh_job_ui()
            self.notify('Request cancelled. The service may still finish processing the request.')

    def analyze(self):
        self.run_job('analysis')

    def send_chat(self,question=None):
        if self.busy:
            return
        if not self.ready_for_ai():
            return
        if not isinstance(question,str):
            question=self.chat_input.text().strip()
        if not question.strip():
            return
        self.chat_draft=''
        if self.view=='assistant':
            self.chat_input.clear()
        self.chat.append(('You',question.strip()))
        self.run_job('chat',question.strip())

    def job_finished(self,payload):
        if self._closing or payload.get('job_id')!=self.active_job:
            return
        self.busy=False
        self.active_job=None
        if payload['measurement_id']!=self.current_id or payload['metrics']!=self.metrics:
            self.refresh_job_ui()
            self.notify('Metrics changed while the request was running. Start a new analysis.')
            return
        if payload['error']:
            self.refresh_job_ui()
            QMessageBox.warning(self,'AI Unavailable',payload['error'])
            self.notify('Could not get a response from the model.')
            return
        if payload['kind']=='analysis':
            self.analysis=payload['result']
            try:
                self.repo.save_analysis(self.current_id,self.analysis,self.metrics)
            except (sqlite3.Error,OSError) as exc:
                self.storage_error(exc)
                self.notify('Analysis received, but could not be saved to disk.')
            else:
                self.notify('AI analysis and plan saved.' if self.analysis.mode=='ai' else 'Plan paused pending medical review.')
        else:
            self.chat.append(('ORVEXA',payload['result']))
            self.notify('Model response received.')
        if payload['kind']=='analysis' and self.view in ('overview','training'):
            self.show_view(self.view,preserve_scroll=True)
        else:
            if payload['kind']=='analysis' and self.view=='assistant' and self.ai_widget is not None:
                old=self.ai_widget
                parent=old.parentWidget()
                parent.layout().replaceWidget(old,self.ai_card())
                old.hide()
                old.deleteLater()
            self.refresh_job_ui()

    def exercise_details(self,exercise):
        dialog=QDialog(self)
        dialog.setWindowTitle('ORVEXA · '+exercise.name)
        dialog.setMinimumWidth(450)
        dialog.setMaximumWidth(600)
        box=QVBoxLayout(dialog)
        box.setContentsMargins(26,25,26,25)
        box.setSpacing(17)
        box.addWidget(label(exercise.equipment+'  /  '+str(exercise.minutes)+' MIN',10,'#60cce3'))
        box.addWidget(label(exercise.name,23,'#e2f2ff',wrap=True))
        box.addWidget(label(exercise.description,12,'#93aec5',wrap=True))
        instructions=QTextBrowser()
        instructions.setPlainText(exercise.steps)
        instructions.setMinimumHeight(160)
        instructions.setMaximumHeight(240)
        instructions.setOpenExternalLinks(False)
        box.addWidget(instructions)
        box.addWidget(label('Actual exercise parameters must be agreed with mission specialists.',10,'#bda97c',wrap=True))
        box.addWidget(button('Got It',dialog.accept,primary=True))
        dialog.exec()
        dialog.deleteLater()

    def start_workout(self):
        plan=self.get_plan()
        if not plan:
            self.notify('No plan is currently available. Consult the mission medical officer or request a new analysis.')
            return
        mode='ai' if self.analysis and self.analysis.mode=='ai' else 'sample'
        dialog=WorkoutDialog(plan,mode,self)
        try:
            dialog.exec()
            if dialog.finished_session:
                try:
                    self.repo.add_session(round(dialog.elapsed),dialog.completed,plan,mode)
                except (sqlite3.Error,OSError) as exc:
                    self.storage_error(exc)
                    return
                self.show_view(self.view,preserve_scroll=True)
                self.notify(f'Workout saved: {dialog.completed} exercises, {dialog.elapsed/60:.1f} min on the timer.')
        finally:
            dialog.deleteLater()

    def export_report(self):
        file_name,file_filter=QFileDialog.getSaveFileName(self,'Save Report',f'ORVEXA-{datetime.now():%Y-%m-%d}.json','JSON (*.json);;CSV (*.csv)')
        if not file_name:
            return
        try:
            path=Path(file_name)
            format_name=path.suffix.lower().lstrip('.') if path.suffix.lower() in ('.csv','.json') else ('csv' if file_filter.startswith('CSV') else 'json')
            if path.suffix.lower() not in ('.csv','.json'):
                path=Path(str(path)+'.'+format_name)
                if path.exists() and QMessageBox.question(self,'Replace File?',f'The file {path.name} already exists. Replace it?',
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
                    return
            data={**self.repo.export(),'profile':{'name':self.name,'role':self.role,'baseline_heart':self.metrics.baseline_heart}}
            save_report(path,data,format_name)
            self.notify('Report saved: '+str(path))
        except (OSError,sqlite3.Error,ValueError) as exc:
            QMessageBox.warning(self,'Unable to Save',str(exc))

    def show_help(self):
        QMessageBox.information(self,'How to Use ORVEXA',
            '1. Select “Enter Data” and enter resting measurements.\n\n'
            '2. In Settings, choose OpenAI and enter an API key, or choose local Ollama with a model installed.\n\n'
            '3. Select “Run AI Analysis” to receive an explanation and a draft plan. Without a connected model, only the clearly labeled sample workout is available.\n\n'
            '4. Start a workout. The timer tracks actual elapsed time; the log is stored in SQLite.\n\n'
            '5. Export JSON or CSV files from Reports.\n\n'
            'This is a research prototype. No sensors are connected. Medical decisions and actual exercise loads must be determined by the mission medical officer.')

    def closeEvent(self,event):
        self._closing=True
        self.active_job=None
        self.settings_draft=None
        self.config=replace(self.config,api_key='')
        self.repo.close()
        super().closeEvent(event)
