import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QHBoxLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QMessageBox, QWidget, QTextBrowser)
from .domain import Metrics
from .widgets import label, button, row

class MetricsDialog(QDialog):
    def __init__(self, metrics, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ORVEXA · New Measurement')
        self.setMinimumWidth(480)
        box=QVBoxLayout(self)
        box.setContentsMargins(28,25,28,25)
        box.setSpacing(14)
        box.addWidget(label('How are you feeling?',23,'#edf7ff'))
        box.addWidget(label('Enter resting measurements. They will be saved on this computer.',10,'#829ab3',wrap=True))
        grid=QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        self.fields={}
        specs=[('heart','Heart Rate (bpm)',30,220,0),('spo2','SpO₂ (%)',50,100,1),
               ('temperature','Temperature (°C)',32,43,1),('fatigue','Fatigue (0–10)',0,10,0),
               ('baseline_heart','Heart Rate Baseline (bpm)',35,110,0)]
        for index,(key,title,minimum,maximum,decimals) in enumerate(specs):
            field=QDoubleSpinBox() if decimals else QSpinBox()
            if decimals:
                field.setDecimals(decimals)
                field.setSingleStep(.1)
            field.setRange(minimum,maximum)
            field.setValue(getattr(metrics,key))
            self.fields[key]=field
            column=index%2
            line=(index//2)*2
            grid.addWidget(label(title,10,'#91aac1'),line,column)
            grid.addWidget(field,line+1,column)
        sleepbox=QWidget()
        sleep_layout=QHBoxLayout(sleepbox)
        sleep_layout.setContentsMargins(0,0,0,0)
        sleep_layout.setSpacing(7)
        self.sleep_hours=QSpinBox()
        self.sleep_hours.setRange(0,16)
        self.sleep_minutes=QSpinBox()
        self.sleep_minutes.setRange(0,59)
        total=round(metrics.sleep_hours*60)
        self.sleep_hours.setValue(total//60)
        self.sleep_minutes.setValue(total%60)
        self.sleep_hours.valueChanged.connect(lambda hours:self.sleep_minutes.setMaximum(0 if hours==16 else 59))
        self.sleep_minutes.setMaximum(0 if total//60==16 else 59)
        self.sleep_hours.setSuffix(' h')
        self.sleep_minutes.setSuffix(' min')
        sleep_layout.addWidget(self.sleep_hours)
        sleep_layout.addWidget(self.sleep_minutes)
        grid.addWidget(label('Sleep Duration',10,'#91aac1'),4,1)
        grid.addWidget(sleepbox,5,1)
        box.addLayout(grid)
        self.symptoms=QCheckBox('Pain, dizziness, or unusual discomfort is present')
        self.symptoms.setChecked(metrics.symptoms)
        box.addWidget(self.symptoms)
        box.addWidget(label('No sensors are connected. Metrics are entered manually.\nAgree on actual exercise loads with the mission medical officer.',9,'#66859b',wrap=True))
        box.addLayout(row(None,button('Cancel',self.reject,secondary=True),button('Save Measurements',self.confirm,primary=True)))

    def metrics(self):
        values={key:field.value() for key,field in self.fields.items()}
        values['sleep_hours']=self.sleep_hours.value()+self.sleep_minutes.value()/60
        values['symptoms']=self.symptoms.isChecked()
        return Metrics(**values).validate()

    def confirm(self):
        try:
            self.metrics()
        except ValueError as exc:
            QMessageBox.warning(self,'Check Data',str(exc))
            return
        self.accept()

class WorkoutDialog(QDialog):
    def __init__(self, plan, mode, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ORVEXA · Workout')
        self.setMinimumWidth(500)
        self.setMaximumWidth(620)
        self.plan=tuple(plan)
        if not self.plan:
            raise ValueError('There are no exercises in this workout.')
        self.mode=mode
        self.index=0
        self.completed=0
        self.elapsed=0.0
        self.step_elapsed=0.0
        self.running=False
        self.finished_session=False
        self.last_tick=None
        self.timer=QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.finished.connect(self.stop_timer)
        self.box=QVBoxLayout(self)
        self.box.setContentsMargins(30,26,30,25)
        self.box.setSpacing(16)
        self.build_step()

    def clear(self):
        while self.box.count():
            item=self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                layout=item.layout()
                while layout.count():
                    child=layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                layout.deleteLater()

    def build_step(self):
        self.clear()
        exercise=self.plan[self.index]
        self.box.addWidget(label(f'{"AI-GENERATED PLAN" if self.mode=="ai" else "SAMPLE PLAN"}  /  {self.index+1} OF {len(self.plan)}',9,'#65cee7'))
        self.box.addWidget(label(exercise.name,23,'#edf7ff',wrap=True))
        self.box.addWidget(label(f'{exercise.equipment} · {exercise.minutes} min',11,'#8ea8c0'))
        self.clock=label('',50,'#89e4fb')
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock.setMinimumHeight(100)
        self.box.addWidget(self.clock)
        note=label('TIME REMAINING IN EXERCISE',9,'#6c8ca4')
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.addWidget(note)
        instructions=QTextBrowser()
        instructions.setPlainText(exercise.steps)
        instructions.setMinimumHeight(120)
        instructions.setMaximumHeight(200)
        instructions.setOpenExternalLinks(False)
        self.box.addWidget(instructions)
        self.box.addWidget(label('Stop if you experience pain, dizziness, or unusual shortness of breath.\nExercise load and technique must be determined by a mission specialist.',10,'#cfb789',wrap=True))
        self.toggle=button('Start',self.toggle_timer,icon='play',primary=True)
        self.toggle.setAutoDefault(False)
        next_button=button('Finish' if self.index==len(self.plan)-1 else 'Next',self.next_step,icon='arrow')
        next_button.setAutoDefault(False)
        self.box.addLayout(row(self.toggle,next_button))
        self.box.addWidget(label('Selecting “Next” marks the exercise as completed.\nThe log records the actual time tracked by the timer.',9,'#68849c',wrap=True))
        self.update_clock()

    def update_clock(self):
        left=max(0,self.plan[self.index].minutes*60-int(self.step_elapsed))
        self.clock.setText(f'{left//60:02d}:{left%60:02d}')

    def tick(self):
        if not self.running:
            return
        now=time.monotonic()
        delta=max(0,now-self.last_tick)
        self.last_tick=now
        remaining=max(0,self.plan[self.index].minutes*60-self.step_elapsed)
        delta=min(delta,remaining)
        self.step_elapsed+=delta
        self.elapsed+=delta
        self.update_clock()
        if self.step_elapsed>=self.plan[self.index].minutes*60:
            self.pause()
            self.toggle.setText('Exercise Completed')
            self.toggle.setEnabled(False)

    def pause(self):
        self.running=False
        self.timer.stop()
        self.toggle.setText('Resume')

    def toggle_timer(self):
        if self.finished_session or self.step_elapsed>=self.plan[self.index].minutes*60:
            return
        if self.running:
            self.tick()
            if self.running:
                self.pause()
        else:
            self.running=True
            self.last_tick=time.monotonic()
            self.timer.start()
            self.toggle.setText('Pause')

    def next_step(self):
        if self.finished_session:
            return
        if self.running:
            self.tick()
        self.pause()
        self.completed+=1
        if self.index+1<len(self.plan):
            self.index+=1
            self.step_elapsed=0
            self.build_step()
        else:
            self.finished_session=True
            self.accept()

    def stop_timer(self):
        self.running=False
        self.timer.stop()

    def reject(self):
        if self.running:
            self.tick()
        self.pause()
        if self.elapsed or self.completed:
            answer=QMessageBox.question(self,'End Workout?','Save the completed portion of this workout to the log?',
                QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if answer==QMessageBox.StandardButton.Cancel:
                return
            if answer==QMessageBox.StandardButton.Save:
                self.finished_session=True
                self.accept()
                return
        super().reject()
